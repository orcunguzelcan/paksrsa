import pythonnet

pythonnet.load("netfx")
import time
import binascii
import sound_config
import datetime
import video_stream
import cv2
import os
import numpy as np
import paks_database
import database_config as dbconfig
import threading
from Logger import LOGGER
import clr
import sys

# --- AYARLAR ---
base_dir = os.path.dirname(os.path.abspath(__file__))
native_dll_dir = os.path.join(base_dir, "x64")
os.environ["PATH"] = native_dll_dir + os.pathsep + os.environ.get("PATH", "")
sys.path.append(base_dir)

try:
    clr.AddReference("Bio.TrustFinger")
    from Aratek.TrustFinger import TrustFingerManager, TrustFingerDevice, FingerPosition, LedStatus, \
        TrustFingerException
except Exception as e:
    LOGGER.WriteLog(f"DLL Import Error: {e}")

read_finger_per_crime_check_time = True
fingerprint_check_lock = threading.Lock()
database = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)
imageRootPath = "C:/PAKS-STORAGE"
imagePath = str()

# Global Cihaz Değişkeni
dev = None


def init_fingerprint_sensor():
    try:
        TrustFingerManager.GlobalInitialize()
        device = TrustFingerDevice()
        device.Open(0)
        return device
    except Exception as e:
        LOGGER.WriteLog("Sensor Init Error: " + str(e))
        return None


def set_led(dev, index: int, status: LedStatus):
    """LED kontrolü (Hata alsa bile programı durdurmaz)"""
    try:
        if dev: dev.SetLedStatus(index, status)
    except:
        pass


def is_device_open(dev) -> bool:
    try:
        return dev is not None and dev.IsOpen
    except:
        return False


# --- YENİ FONKSİYON: DIŞARIDAN İPTAL ---
def cancel_scanning():
    """
    Timeout veya pencere kapanması durumunda dışarıdan çağrılır.
    Sensör ışığını ANINDA kapatır.
    """
    global dev
    video_stream.fingerprint_thread_active = False  # Bayrağı indir
    LOGGER.WriteLog("Tarama iptal edildi, LED kapatılıyor...")

    # Thread'in işini bitirmesini beklemeden ışığı zorla kapat
    # Lock kullanarak thread ile çakışmayı önle
    if dev:
        try:
            # Thread o sırada sensörü kullanıyor olabilir, try-except önemli
            dev.SetLedStatus(0, LedStatus.Off)
        except:
            pass


# --- SNAPSHOT FONKSİYONLARI ---
def snapshot_effect(frame):
    whiteFrame = 255 * np.ones((480, 800, 3), np.uint8)
    try:
        cv2.namedWindow("window", cv2.WINDOW_NORMAL)
        cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.imshow("window", whiteFrame)
        cv2.waitKey(750)
        cv2.imshow("window", frame)
        cv2.waitKey(1500)
        time.sleep(0.5)
        cv2.destroyAllWindows()
    except:
        pass


def take_snapshot(uID, frame):
    global imagePath
    timeStamp = datetime.datetime.now()
    cameraPath = os.path.join('Photos', str(uID), str(timeStamp.year), str(timeStamp.month), str(timeStamp.day))
    personFile = timeStamp.strftime("%Y%m%d%H%M%S%f")
    try:
        out_dir = os.path.join(imageRootPath, cameraPath)
        os.makedirs(out_dir, mode=0o777, exist_ok=True)
        local_frame = frame.copy() if frame is not None else frame
        if local_frame is None: return
        try:
            bgr = cv2.cvtColor(local_frame, cv2.COLOR_RGB2BGR)
        except:
            bgr = local_frame
        out_file = personFile + ".jpg"
        img_path_capture = os.path.join(out_dir, out_file)
        if cv2.imwrite(img_path_capture, bgr):
            imagePath = os.path.join(cameraPath, out_file).replace("\\", "/")
            try:
                snapshot_effect(bgr)
            except:
                pass
    except Exception as e:
        LOGGER.WriteLog("Snapshot Error: " + str(e))


# --- TARAMA FONKSİYONU ---
def find_finger_1_to_N(scan_window, root_main):
    global finger, imagePath, read_finger_per_crime_check_time, dev

    retry_count = 0
    while (dev is None or not is_device_open(dev)):
        if not video_stream.fingerprint_thread_active: return
        dev = init_fingerprint_sensor()
        if dev is None:
            time.sleep(1)
            retry_count += 1
            if retry_count > 5: time.sleep(2)

    LOGGER.WriteLog("1:N Tarama Modu Başladı.")

    while video_stream.fingerprint_thread_active:
        fingerResult = None

        # --- BLOK 1: SENSÖR OKUMA ---
        with fingerprint_check_lock:
            try:
                # İptal edildiyse hemen çık
                if not video_stream.fingerprint_thread_active:
                    set_led(dev, 0, LedStatus.Off)
                    return

                set_led(dev, 0, LedStatus.On)

                # Bu işlem bloklayabilir (bekletebilir)
                bmp_data = dev.CaptureBitmapData(20)

                # UYANDIKTAN SONRA KONTROL: Eğer o sırada iptal edildiyse çık
                if not video_stream.fingerprint_thread_active:
                    set_led(dev, 0, LedStatus.Off)
                    return

                if bmp_data is None or bmp_data.FingerprintImageData is None:
                    continue

                fingerResult = dev.ExtractFeature(FingerPosition.UnKnow)
            except Exception:
                pass
            finally:
                # Her döngü sonunda LED'i kapat (Bir sonraki turda tekrar yakacak)
                # Bu, ışığın takılı kalmasını önler
                set_led(dev, 0, LedStatus.Off)

        # --- KRİTİK KONTROL ---
        # Eğer yukarıdaki işlemler sırasında timeout olduysa
        # aşağıya inip "Hata Sesi" çalma, sessizce çık.
        if not video_stream.fingerprint_thread_active:
            return

        # --- BLOK 2: SONUÇ ANALİZİ ---
        if fingerResult is None or fingerResult.FeatureData is None:
            # Parmak okunamadıysa hata verip başa dön (User İsteği)
            # Ancak process hala aktifse yap bunu
            if video_stream.fingerprint_thread_active:
                LOGGER.WriteLog("Okuma başarısız.")
                sound_config.play_sound(sound_config.soundError)

                # Hata durumunda ana ekrana dön
                video_stream.fingerprint_thread_active = False
                try:
                    scan_window.destroy()
                    root_main.deiconify()
                except:
                    pass
                return
            else:
                return  # Sessizce çık

        # --- BLOK 3: VERİTABANI SORGUSU ---
        live_template = fingerResult.FeatureData
        all_fingerprints = database.selectFingerPrintsTable()

        matched_person_id = None
        matched_tckn = None
        isFingerFound = False

        for i, row in enumerate(all_fingerprints):
            if not video_stream.fingerprint_thread_active: return

            db_template_hex = row[1]
            if db_template_hex is None: continue
            try:
                tempInfo = db_template_hex.replace("'", "").strip()
                tempInfoBytes = System.Array[System.Byte](list(binascii.unhexlify(tempInfo)))
                result = dev.Verify(3, live_template, tempInfoBytes)
                if result.get_IsMatch():
                    finger_id = row[0]
                    matched_person_id = database.selectPersonId(finger_id)
                    matched_tckn = database.selectTCNo(matched_person_id)
                    isFingerFound = True
                    break
            except:
                continue

        if not video_stream.fingerprint_thread_active: return

        # --- BLOK 4: SONUÇ BİLDİRİMİ ---
        if isFingerFound:
            if len(database.selectBlacklistPersonResult(matched_person_id)) > 0:
                database.insertBlacklist(matched_person_id)
                sound_config.play_sound(sound_config.soundAlarm)

            crimes = database.selectPersonCrimesTable(matched_person_id)
            imza_atildi = False

            if len(crimes) > 0:
                for c in crimes:
                    check_times = database.selectIdFromPersonCrimeCheckTimesTable(c[0])
                    if len(check_times) > 0:
                        take_snapshot(matched_tckn, video_stream.frame)
                        database.updateCrimeCheckTimes(
                            printStatus='1',
                            imagePath=imagePath,
                            crimeResult=c[0],
                            crime_check_time_id=check_times[0][0]
                        )
                        imza_atildi = True
                        if read_finger_per_crime_check_time: break

            if imza_atildi:
                sound_config.play_sound(sound_config.soundSuccess)
            else:
                sound_config.play_sound(sound_config.soundNextHour)

            time.sleep(1.5)
            video_stream.fingerprint_thread_active = False
            try:
                scan_window.destroy()
                root_main.deiconify()
            except:
                pass
            return

        else:
            LOGGER.WriteLog("Eşleşme yok.")
            sound_config.play_sound(sound_config.soundUndefined)
            time.sleep(2)

            video_stream.fingerprint_thread_active = False
            try:
                scan_window.destroy()
                root_main.deiconify()
            except:
                pass
            return