import serial
import time
import binascii
import sound_config
import datetime
import time
import video_stream
import cv2
import os
import numpy as np
import paks_database
import database_config as dbconfig
import threading
from Logger import LOGGER
import subprocess

import clr
import sys
import System

read_finger_per_crime_check_time = True


fingerprint_check_lock = threading.Lock()
database = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)

imageRootPath = "C:/PAKS-STORAGE"
imagePath = str()

# Yolları ayarla
base_dir = os.path.dirname(os.path.abspath(__file__))
native_dll_dir = os.path.join(base_dir, "x64")
os.environ["PATH"] = native_dll_dir + os.pathsep + os.environ.get("PATH", "")
sys.path.append(base_dir)

clr.AddReference("Bio.TrustFinger")

from Aratek.TrustFinger import (
    TrustFingerManager, TrustFingerDevice,
    FingerPosition, LedStatus, TrustFingerException
    )

def init_fingerprint_sensor():
    try:            
        TrustFingerManager.GlobalInitialize()

        # Cihazı aç
        dev = TrustFingerDevice()
        dev.Open(0)        
        return dev
    except Exception as e:
        print("Fingerprint Sensor Init Exception: " + str(e))
        LOGGER.WriteLog("Fingerprint Sensor Init Exception: " + str(e))
        
dev = init_fingerprint_sensor()
def set_led(dev, index: int, status: LedStatus, duration: float = None):
    """
    LED durumunu ayarla. İsteğe bağlı süreyle otomatik kapatma yapılabilir.

    Args:
        dev: TrustFingerDevice nesnesi
        index: 0 = yeşil, 1 = kırmızı
        status: LedStatus.On veya LedStatus.Off
        duration: float (saniye) → Eğer verilirse süre kadar yanar sonra söner
    """
    try:
        dev.SetLedStatus(index, status)
        if duration is not None and status == LedStatus.On:
            time.sleep(duration)
            dev.SetLedStatus(index, LedStatus.Off)
    except TrustFingerException as e:
        dev.SetLedStatus(index, LedStatus.Off)
        print(f"LED ayarlanamadı (index={index}, status={status}): Hata kodu = {e.ErrorCode}")

def is_device_open(dev) -> bool:
    return dev.IsOpen
    
def snapshot_effect(frame):    
    #whiteFrame = 255 * np.ones((600,1024,3), np.uint8) 
    whiteFrame = 255 * np.ones((480,800,3), np.uint8) 
    # "window" adıyla pencere oluştur
    cv2.namedWindow("window", cv2.WINDOW_NORMAL)
    
    # Pencereyi tam ekran yap
    cv2.setWindowProperty("window", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("window",whiteFrame)
    cv2.waitKey(750)
    cv2.imshow("window",frame)
    cv2.waitKey(1500)
    time.sleep(0.5)
#             cv2.rotate(frame, cv2.cv2.ROTATE_180)
    cv2.destroyAllWindows()
    

def take_snapshot(uID, frame):
    """
    Fotoğraf kaydetme akışı sadece güvenlikle ilgili düzeltmelerle güncellendi:
    - Path'ler os.path.join ile kuruluyor (başında '/' yok).
    - Dosya adı mikro saniye içeriyor (çakışma yok).
    - Frame güvenli kopya ile işleniyor.
    - Önce kaydet, sonra snapshot_effect (gecikme kaydetmeyi etkilemesin).
    - cv2.imwrite başarı döndürürse global imagePath set ediliyor.
    """
    global imagePath

    timeStamp = datetime.datetime.now()
    # / ile başlayan relatif path sorununu önlemek için join kullan
    cameraPath = os.path.join('Photos', str(uID), str(timeStamp.year), str(timeStamp.month), str(timeStamp.day))
    personFile = timeStamp.strftime("%Y%m%d%H%M%S%f")  # mikro saniye ile çakışmayı önle

    try:
        # Mutlak çıktı klasörü
        out_dir = os.path.join(imageRootPath, cameraPath)
        os.umask(0)
        os.makedirs(out_dir, mode=0o777, exist_ok=True)

        # Frame'i güvenle kopyala (kilit yoksa en azından kopya al)
        local_frame = None
        try:
            if frame is not None:
                local_frame = frame.copy()
        except Exception:
            # copy başarısızsa orijinali kullanmayı dene
            local_frame = frame

        # Geçerli frame mi?
        if (local_frame is None) or (not isinstance(local_frame, np.ndarray)) or (local_frame.size == 0) or (np.sum(local_frame) == 0):
            imagePath = None
            LOGGER.WriteLog("Fotoğraf çekme başarısız: boş veya geçersiz frame")
            return

        # Renk dönüşümü (RGB geldiyse)
        try:
            bgr = cv2.cvtColor(local_frame, cv2.COLOR_RGB2BGR)
        except Exception:
            # Zaten BGR olabilir; dönüşüm hatasında orijinali kullan
            bgr = local_frame

        # Önce kaydet (bloklayıcı efektlerden önce)
        out_file = personFile + ".jpg"
        img_path_capture = os.path.join(out_dir, out_file)
        ok = cv2.imwrite(img_path_capture, bgr)

        if ok:
            # Global imagePath'i yalnızca başarıda set et (relatif, normalize edilmiş)
            imagePath = os.path.join(cameraPath, out_file).replace("\\", "/")
            LOGGER.WriteLog(f"Fotoğraf çekme başarılı: {img_path_capture}")

            # Görsel efekti KAYITTAN SONRA uygula (özellik korunur, kaydetmeyi geciktirmez)
            try:
                snapshot_effect(bgr)
            except Exception as e:
                LOGGER.WriteLog("Snapshot effect error: " + str(e))
        else:
            imagePath = None
            LOGGER.WriteLog("Fotoğraf çekme başarısız: cv2.imwrite False döndü")

    except Exception as e:
        LOGGER.WriteLog("Exception: " + str(e))

#def init_fingerprint_sensor():
#    global uart,finger
#    try:
#        if uart and uart.is_open:
#            uart.close()
#        uart = serial.Serial("/dev/ttyS0", baudrate=57600, timeout=1)
#        finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)
#        return True
#    except:
#        return False

#def init_fingerprint_sensor(max_retries=5, delay=2):
#    global uart, finger
#    for attempt in range(1, max_retries + 1):
#        try:
#            if uart and uart.is_open:
#                uart.close()
#            uart = serial.Serial("COM3", baudrate=57600, timeout=1)
#            finger = adafruit_fingerprint.Adafruit_Fingerprint(uart)
#            print(f"Parmak izi sensörü başarıyla başlatıldı. Deneme: {attempt}")
#            return True
#        except Exception as e:
#            print(f"Deneme {attempt} başarısız: {e}")
#            time.sleep(delay)
#    
#    print("Tüm denemeler başarısız. rc.local servisi yeniden başlatılıyor...")
#    try:
#        subprocess.run(["sudo", "systemctl", "restart", "rc-local"], check=True)
#        print("rc.local servisi başarıyla yeniden başlatıldı.")
#    except subprocess.CalledProcessError as e:
#        print(f"rc.local servisi yeniden başlatılamadı: {e}")
#    
#    return False 
        
def find_finger(fingerprint_list, person_id_info, person_tckn_info):
    global finger,imagePath,read_finger_per_crime_check_time,dev
    fingerResult=None    
    
    while (dev is None or not is_device_open(dev)):        
        dev = init_fingerprint_sensor()
        
    while video_stream.fingerprint_thread_active:
        print("fp_thread_active")
        with fingerprint_check_lock:
            try:
                print("before set_led")
                set_led(dev,0,LedStatus.On)
                print("after set_led")
                bmp_data = dev.CaptureBitmapData(20)
                while video_stream.fingerprint_thread_active and (bmp_data is None or bmp_data.FingerprintImageData is None):
                    bmp_data = dev.CaptureBitmapData(20)
                    if not video_stream.fingerprint_thread_active:
                        return
                    continue
                fingerResult = dev.ExtractFeature(FingerPosition.UnKnow)                
            except TrustFingerException as e:
                LOGGER.WriteLog("Fingerprint Scan Error")
                sound_config.play_sound(sound_config.soundError)
                if e.HResult == -221:
                    print("Henüz parmak yok, bekleniyor...")
                else:
                    print(f"Hata oluştu: {e}")
                pass
            finally:
                set_led(dev, 0,LedStatus.Off)
                
            if fingerResult is None or fingerResult.FeatureData is None:
                continue
                
            live_template = fingerResult.FeatureData            
                
            last_success_fingerprint_time = datetime.datetime.now()
            isEffectedAnyRow=False
            isEffectedAnyRowDay=False
            isFingerFound=False
            video_stream.first_call_begin = datetime.datetime.now()
            for i in range(len(fingerprint_list)):
                tempInfo = fingerprint_list[i][1].replace("'", "")
                tempInfo = System.Array[System.Byte](list(binascii.unhexlify(tempInfo)))
                result = dev.Verify(3, live_template, tempInfo)  
                if result.get_IsMatch():
                    blacklistPersonResult = database.selectBlacklistPersonResult(person_id_info)
                    isFingerFound=True
                    
                    if len(blacklistPersonResult) > 0:
                        database.insertBlacklist(person_id_info)
                        sound_config.play_sound(sound_config.soundAlarm)
                    
            crime_result = database.selectPersonCrimesTable(person_id_info)
            
            if isFingerFound and len(crime_result) > 0:
                for j in range(len(crime_result)):
                    crime_check_time_result_id = database.selectIdFromPersonCrimeCheckTimesTable(crime_result[j][0])
                    
                    if len(crime_check_time_result_id) > 0:
                        take_snapshot(person_tckn_info, video_stream.frame)
                        effectedRows=database.updateCrimeCheckTimes(printStatus='1', imagePath=imagePath, crimeResult=crime_result[j][0],crime_check_time_id=crime_check_time_result_id[0][0])
                        if effectedRows>0:
                            isEffectedAnyRow = True
                            time.sleep(0.5)
                            if read_finger_per_crime_check_time:
                                break
                    
                    
                if not isEffectedAnyRow:
                    for k in range(len(crime_result)):
                        crime_check_time_result_id_day_check = database.selectIdFromPersonCrimeCheckTimesTable(crime_result[k][0], day_check=True)
                        if len(crime_check_time_result_id_day_check)>0:
                            take_snapshot(person_tckn_info, video_stream.frame)
                            effectedRows=database.updateCrimeCheckTimes(printStatus='3', imagePath=imagePath, crimeResult=crime_result[k][0], crime_check_time_id=crime_check_time_result_id_day_check[0][0])
                            if effectedRows>0:
                                isEffectedAnyRowDay = True
                                time.sleep(0.5)
                                if read_finger_per_crime_check_time:
                                    break
                           
                if isEffectedAnyRow or isEffectedAnyRowDay:
                    sound_config.play_sound(sound_config.soundSuccess)
                else:
                    sound_config.play_sound(sound_config.soundNextday)
                    video_stream.fingerprint_thread_active=False
                    return                    
                    
                    
            if not isFingerFound or not(isEffectedAnyRow or isEffectedAnyRowDay):
                sound_config.play_sound(sound_config.soundError)
            time.sleep(2)
