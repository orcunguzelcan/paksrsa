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
import atexit

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


# --- GÜVENLİ KAPATMA ---
def release_device():
    """Program kapanırken çalışır."""
    global dev
    try:
        if dev is not None:
            try:
                dev.SetLedStatus(0, LedStatus.Off)
            except:
                pass
            if dev.IsOpen:
                dev.Close()
                LOGGER.WriteLog("Parmak izi sensörü donanım olarak serbest bırakıldı.")
    except Exception as e:
        LOGGER.WriteLog(f"Sensör kapatma hatası: {e}")
    finally:
        dev = None


atexit.register(release_device)


def init_fingerprint_sensor():
    global dev
    try:
        if dev is not None and dev.IsOpen:
            return dev
        TrustFingerManager.GlobalInitialize()
        new_dev = TrustFingerDevice()
        new_dev.Open(0)
        LOGGER.WriteLog("Sensör başarıyla başlatıldı.")
        return new_dev
    except Exception as e:
        LOGGER.WriteLog("Sensor Init Error: " + str(e))
        release_device()
        return None


def set_led(device, index: int, status: LedStatus):
    try:
        if device and device.IsOpen:
            device.SetLedStatus(index, status)
    except:
        pass


def is_device_open(device) -> bool:
    try:
        return device is not None and device.IsOpen
    except:
        return False


# --- DÜZELTİLDİ: UI'DAN ASLA BLOCKING ÇAĞRI YAPMA ---
def cancel_scanning():
    """
    Sadece log yazar ve bayrağı indirir.
    Donanıma komut göndermez çünkü deadlock riski vardır.
    """
    video_stream.fingerprint_thread_active = False
    LOGGER.WriteLog("Tarama iptal isteği alındı (Donanım arka planda kapanacak).")


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


def find_finger_1_to_N(scan_window, root_main):
    global finger, imagePath, read_finger_per_crime_check_time, dev

    try:
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

            with fingerprint_check_lock:
                try:
                    # Döngü başında kontrol
                    if not video_stream.fingerprint_thread_active:
                        break

                    set_led(dev, 0, LedStatus.On)

                    # Bu fonksiyon bloklayabilir. Ancak UI artık bunu beklemiyor.
                    # Eğer çok uzun sürerse UI kapanır, bu thread arkada devam eder,
                    # bitince finally bloğuna düşer ve ışığı kapatır.
                    bmp_data = dev.CaptureBitmapData(20)

                    # Capture sonrası kontrol
                    if not video_stream.fingerprint_thread_active:
                        break

                    if bmp_data is None or bmp_data.FingerprintImageData is None:
                        continue

                    fingerResult = dev.ExtractFeature(FingerPosition.UnKnow)
                except Exception:
                    pass
                finally:
                    # Döngü içindeyken her turda ışığı kapatıp açma mantığı
                    # Eğer döngüden çıkılıyorsa en dıştaki finally kapatacak
                    set_led(dev, 0, LedStatus.Off)

            if not video_stream.fingerprint_thread_active:
                break

            # --- Okuma Başarısız ---
            if fingerResult is None or fingerResult.FeatureData is None:
                if video_stream.fingerprint_thread_active:
                    LOGGER.WriteLog("Okuma başarısız.")
                    sound_config.play_sound(sound_config.soundError)
                    video_stream.fingerprint_thread_active = False
                    try:
                        scan_window.destroy()
                        root_main.deiconify()
                    except:
                        pass
                break

            # --- Veritabanı Kontrolü ---
            live_template = fingerResult.FeatureData
            all_fingerprints = database.selectFingerPrintsTable()

            matched_person_id = None
            matched_tckn = None
            isFingerFound = False

            for i, row in enumerate(all_fingerprints):
                if not video_stream.fingerprint_thread_active: break
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

            if not video_stream.fingerprint_thread_active: break

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
                break

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
                break

    finally:
        # --- THREAD BİTERKEN IŞIK KESİN KAPANACAK ---
        # UI bunu beklemez, arka planda sessizce gerçekleşir.
        LOGGER.WriteLog("Tarama döngüsü bitti, sensör kapatılıyor...")
        release_device()