import schedule
import time
import os
import shutil
#import distutils
#from distutils import dir_util
import psutil
#from pyembedded.raspberry_pi_tools.raspberrypi import PI
from Logger import LOGGER
import fingerprint_config as fpconfig

import database_config as dbconfig
import paks_database
from datetime import datetime, timedelta as td
import threading
import video_stream
import cv2
#import select
import subprocess
import ftplib


#camera = video_stream.camera
#camera_lock = video_stream.camera_lock
Server = 'localhost'
Uid = 'paks'
Password = '159753rsa'
Database = 'detectordb'
ntpServer = '192.168.1.85'
fingerprint_check_lock = fpconfig.fingerprint_check_lock
dev = fpconfig.dev
class RoutineJobs:
    
    def __init__(self):
        print("initializing routinejobs")
        self.mode = 0o777
        self.rootFile = "FTP"
        #self.sourceDb = "/var/lib/mysql"
        self.sourcePhotos = "C:/PAKS-STORAGE/Photos"
        #self.pi = PI()
        self.ntpServer = ntpServer
        self.mDatabase = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)
        self.backUpMutex = threading.Lock()
        self.scheduleJobsThread = threading.Thread(target=self.scheduleJobs)
        self.getPath()
        self.scheduleJobsThread.start()
        
    def scheduleJobs(self):        
        schedule.every(10).minutes.do(self.checkUsage)        
        schedule.every(10).minutes.do(self.componentsHealths)
        schedule.every().hours.do(self.checkAbsent)
        schedule.every().hours.do(self.checkPassive)               
        schedule.every().day.at("23:50").do(self.backup_mysql)        
        schedule.every().day.at("01:00").do(self.checkCrimeStatus)
        schedule.every().minute.do(self.runLaravelScheduler)
        schedule.every().day.at("23:55").do(self.backUp, self.sourcePhotos, 'photos')        
        schedule.every().day.at("03:00").do(self.FTPUpload)
        schedule.every().day.at("04:00").do(self.systemRestart)        
        #schedule.every().minutes.do(self.checkCrimeStatus)   
        while True:
            schedule.run_pending()
            time.sleep(1)
    
    def getPath(self):    
        #os.chmod(self.sourceDb, self.mode)
        if not os.path.exists(self.rootFile):
            os.makedirs(self.rootFile,mode=0o777)
               
    def backup_mysql(self):
        try:
            # Backup dizinini hazırla
            backup_dir = os.path.join(self.rootFile, "db")
            os.makedirs(backup_dir, exist_ok=True)

            # Tarihli backup dosya adı
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"mysql_backup_{timestamp}.sql")

            # mysqldump komutu (şifre açık)
            dump_cmd = f"mysqldump -u paks -p159753rsa detectordb > {backup_file}"

            # Komutu çalıştır
            subprocess.run(dump_cmd, shell=True, check=True)

            LOGGER.WriteLog(f"MySQL yedeği alındı: {backup_file}")

        except subprocess.CalledProcessError as e:
            LOGGER.WriteLog(f"mysqldump hatası: {e}")
        except Exception as e:
            LOGGER.WriteLog(f"Yedekleme sırasında hata oluştu: {e}")
    
    def backUp(self, Source, BackupMode):
        with self.backUpMutex:
            try:                
                dailyTime = datetime.now()
                destinationRoot = os.path.join(self.rootFile,BackupMode,str(dailyTime.year),str(dailyTime.month),str(dailyTime.day))

                if not destinationRoot == "":
                    os.makedirs(destinationRoot, exist_ok=True)
                    tempDestination = destinationRoot 
                    path = Source
                    newPath = tempDestination
                    for item in os.listdir(path):
                        s = os.path.join(path, item)
                        d = os.path.join(newPath, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)  # Python 3.8+
                        else:
                            shutil.copy2(s, d)
                            
                    LOGGER.WriteLog(f"{BackupMode} yedekleme tamamlandı.")
            except subprocess.CalledProcessError as e:
                LOGGER.WriteLog(f"chmod command error: {e}")
            except Exception as e:
                LOGGER.WriteLog(f"Yedekleme sırasında hata oluştu:{e}")
    
    def FTPUpload(self):
        LOGGER.WriteLog("Dosyalar gönderiliyor...")
        
        ftp_host = ntpServer     # <-- ntpServer değişkeninin değeri
        ftp_user = 'rsa'
        ftp_pass = 'qw34qw34'
        ftp_port = 21
        
        def ensure_ftp_directory(ftp, path):
            """Her bir dizin seviyesini tek tek oluşturur"""
            parts = path.replace("\\", "/").split("/")
            for part in parts:
                if not part:
                    continue
                try:
                    ftp.mkd(part)
                except ftplib.error_perm as e:
                    if not str(e).startswith("550"):  # klasör zaten varsa
                        raise
                ftp.cwd(part)

        try:
            with ftplib.FTP() as ftp:
                ftp.connect(ftp_host, ftp_port)
                ftp.login(ftp_user, ftp_pass)

                for root, dirs, files in os.walk(self.rootFile):
                    relative_path = os.path.relpath(root, self.rootFile).replace("\\", "/")
                    
                    ftp.cwd("/")
                    if relative_path != ".":
                        ensure_ftp_directory(ftp,relative_path)
                        
                        

                        
                        

                    for filename in files:
                        file_path = os.path.join(root, filename)
                        with open(file_path, "rb") as file:
                            ftp.storbinary(f'STOR {filename}', file)

                    if relative_path != ".":
                        ftp.cwd("..")

            LOGGER.WriteLog("Dosyalar gönderildi...")        

            # Dosyaları sil
            for item in os.listdir(self.rootFile):
                item_path = os.path.join(self.rootFile, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            LOGGER.WriteLog("Dosyalar silindi.")
            
        except Exception as e:
            LOGGER.WriteLog(f"FTP aktarımında hata oluştu: {e}")
    
    
    
    
    #def FTPUpload(self):
    #    LOGGER.WriteLog("Dosyalar gönderiliyor...")   
    #    
    #    # Sudo ile komutu çalıştırmak
    #    #command = ['sudo', 'ncftpput', '-R', '-u', 'rsa', '-p', 'qw34qw34', '-P', '21', ntpServer, '/', self.rootFile]
    #
    #    # Komutu çalıştır
    #    #subprocess.run(command)
    #    
    #    LOGGER.WriteLog("Dosyalar gönderildi...")        
    # 
    #    #os.system('sudo rm -r ' + self.rootFile + '/*')
    #    LOGGER.WriteLog("Dosyalar silindi...")
        
    def RemoveOldPhotos(self):

        if(os.path.isdir(self.getPath())):   
            
            os.chmod(self.sourceDb, self.mode)
            FD = psutil.disk_usage('/')
            self.mDatabase.insertFDPercent(FD.percent)
            if FD.percent >= 95:        
                
                oneYear = td(days=360)/td(days=1)
                deleteList=list()
                
                for root, directories, files in os.walk(self.sourcePhotos,topdown=False):
                    if FD.percent > 0:
                        for name in files:                
                            diffFromNow = int(datetime.now().timestamp()-(os.path.getmtime(root)))
                    
                            if diffFromNow > oneYear:
                                LOGGER.WriteLog("Removed:{}".format(os.path.join(root, name)))
                                deleteList.append(os.path.join(root, name))                   
                        for name in directories:
                            diffFromNow = int(datetime.now().timestamp()-(os.path.getmtime(root)))               
                            
                            if diff_from_now > oneYear:
                                LOGGER.WriteLog("Removed:{}".format(os.path.join(root, name)))
                                deleteList.append(os.path.join(root, name))                       
                
                    else:
                        break
                    
                if len(deleteList) > 0:
                    LOGGER.WriteLog("1 yıldan önceki fotoğraflar hafıza birimi dolduğu için silindi!")
                
                for i in deleteList:
                    if os.path.isfile(i):
                        os.remove(i)
                    elif os.path.isdir(i):
                        os.rmdir(i)
    
    def systemRestart(self):
        try:
                      
            LOGGER.WriteLog("Servisler yeniden başlatıldı.")      
            os.system('sudo reboot')

        except Exception as e:
            LOGGER.WriteLog("Error: "+e)
            
    def NTPSync(self):
        try:
            os.system(f'sudo ntpdate {self.ntpServer}')
            LOGGER.WriteLog('NTP update successfull.')
        
        except Exception as e:
            LOGGER.WriteLog(f"Error: {e}")
            
    
    def checkUsage(self):
        # RAM kullanımı
        ram = psutil.virtual_memory()
        ramUsage = round(ram.percent)

        # CPU kullanımı
        cpuUsage = round(psutil.cpu_percent(interval=1))

        # CPU sıcaklığı (Windows'ta genellikle desteklenmez)
        cpuTemperature = None
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        cpuTemperature = round(entries[0].current)
                        break
        if cpuTemperature is None:
            cpuTemperature = 0  # Windows'ta desteklenmiyorsa varsayılan değer

        # Disk kullanımı (C:\)
        FD = psutil.disk_usage('C:\\')

        # Veritabanına kaydet
        self.mDatabase.insertFDPercent(FD.percent)        
        self.mDatabase.insertUsage(ramUsage, cpuUsage, cpuTemperature)
    
    
    #def checkUsage(self):        
    #    ram = self.pi.get_ram_info()
    #    ramUsage = round((int(ram[1]) / int(ram[0])) * 100)
    #    cpuUsage = round(float(self.pi.get_cpu_usage()))
    #    cpuTemperature = round((self.pi.get_cpu_temp()))
    #    FD = psutil.disk_usage('/')
    #    self.mDatabase.insertFDPercent(FD.percent)        
    #    self.mDatabase.insertUsage(ramUsage, cpuUsage, cpuTemperature)
        
            
     #Parmak izi sensör çalışma kontrolü
    def check_fingerprint_module(self,dev):
        global fingerprint_check_lock
        if fingerprint_check_lock.acquire(blocking=False):
            try:
                return fpconfig.is_device_open()
            except Exception as e:
                fpconfig.init_fingerprint_sensor()
                LOGGER.WriteLog("Check fingerprint module exception: " + str(e))
            finally:
                fingerprint_check_lock.release()
        LOGGER.WriteLog("Skipped fp_module control due to the lock")
        return True
            
    
    #def check_fingerprint_module(self): 
    #    global fingerprint_check_lock
    #    if fingerprint_check_lock.acquire(blocking=False):
    #        try:                         
    #            return fpconfig.finger.check_module()
    #        except Exception as e: 
    #            init_fingerprint_sensor()
    #            LOGGER.WriteLog(f"Exception occured: {e}")
    #            return False
    #        finally:
    #            fingerprint_check_lock.release()
    #    print("Skipped fp_module control due to the lock")
    #    return True
            
            
    def get_camera_health(self):
        print("camera health check")
        try:
            if video_stream.camera is None:                
                video_stream.camera = video_stream.get_camera_instance()#cv2.VideoCapture(-1)                
            if video_stream.camera is not None:
                status, frame = video_stream.camera.read()
                video_stream.camera.release()
                video_stream.camera = None
                return status
            if not video_stream.fingerprint_thread_active:
                status, frame = video_stream.camera.read()
                video_stream.camera.release()
                video_stream.camera = None
                return status  
            return True
        except Exception as e:
            LOGGER.WriteLog(f"Exception occured: {e}")
            return False
            
    def get_camera_health__(self):
        global camera
        print("sleeping NOWw")
        try:
            if video_stream.camera_lock.acquire(timeout=5):
                print("sleeping1")
                video_stream.camera = video_stream.get_camera_instance()
                if video_stream.camera is not None and video_stream.camera.isOpened():
                    status,_=video_stream.camera.read()
                    print("Sleeping NOW")
                    return status
                return False
        except Exception as e:
            print(e)
            LOGGER.WriteLog(f"Exception occured: {e}")
            return False
        finally:
            print("lock released")
            video_stream.camera_lock.release()
            if video_stream.camera is not None and video_stream.camera.isOpened():
                video_stream.camera.release()
                video_stream.camera=None
    
            
    def componentsHealths(self):        
        global dev
        fp_sensor_health_result = 1 if self.check_fingerprint_module(dev) else 0       
        camera_health_result = 1 if self.get_camera_health() else 0   
        self.mDatabase.insertComponentsHealths(1, fp_sensor_health_result, camera_health_result)    

    # def checkAbsent(self):
    #     checkAbsentResult = self.mDatabase.selectAbsentPeople()
    #     if len(checkAbsentResult) > 0:
    #         self.mDatabase.updateAbsentPeople()
    #         LOGGER.WriteLog("Kaçaklar işaretlendi.")
    
    def checkCrimeStatus(self):
        self.mDatabase.updateCrimeStatus()
        
    #def checkAbsent(self):
    #    checkPersonResult = self.mDatabase.selectAllPersonResults()
    #    for person in checkPersonResult:
    #        checkCrimeId = self.mDatabase.selectAllCrimesForPerson(person[0])
    #        for crimeId in checkCrimeId:
    #            crimeCheckTimes = self.mDatabase.selectAbsentPeople(crimeId[0])
    #            for crimeCheckTimeId in crimeCheckTimes:
    #                self.mDatabase.updateAbsentPeople(crimeCheckTimeId[0])
    
    def checkAbsent(self):
        # Tek tek kişi aramaya gerek yok, veritabanı toplu olarak güncellesin
        self.mDatabase.updateAbsentPeopleBulk()
        LOGGER.WriteLog("Kaçaklar işaretlendi (Eski Yöntem).")

    def checkPassive(self):
        checkPersonResult = self.mDatabase.selectAllPersonResults()
        for person in checkPersonResult:
            checkCrimeId = self.mDatabase.selectAllPassiveCrimesForPerson(person[0])
            for crimeId in checkCrimeId:
                crimeCheckTimes = self.mDatabase.selectAbsentPeople(crimeId[0])
                for crimeCheckTimeId in crimeCheckTimes:
                    self.mDatabase.updatePassivePeople(crimeCheckTimeId[0])
                    
    def runLaravelScheduler(self):
        """Laravel schedule:run komutu ile tüm zamanlanmış görevleri çalıştır"""
        try:
            LOGGER.WriteLog("Laravel schedule:run komutu çalıştırılıyor...")

            # Laravel proje dizini (mevcut dizin)
            # Farklı dizinlerde ise: project_path =  veya 'C:\\xampp\\htdocs\\paks'
            # Linux için project_path = '/home/pi/laravel-project'
            # Windows için project_path = 'C:\\paks'
            project_path = 'C:\\paks'

            result = subprocess.run(
                ['php', 'artisan', 'schedule:run'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120  # 120 saniye timeout (tüm tasklar için)
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output and "No scheduled commands are ready to run" not in output:
                    LOGGER.WriteLog(f"Laravel Scheduler Başarılı: {output}")
                else:
                    LOGGER.WriteLog("Laravel Scheduler: Çalışacak zamanlanmış görev yok")
                return True
            else:
                error = result.stderr.strip()
                LOGGER.WriteLog(f"Laravel Scheduler Hatası: {error}")
                return False

        except subprocess.TimeoutExpired:
            LOGGER.WriteLog("Laravel scheduler timeout (120 saniye)")
            return False
        except FileNotFoundError:
            LOGGER.WriteLog("Laravel scheduler hatası: php bulunamadı - PATH kontrol edin")
            return False
        except Exception as e:
            LOGGER.WriteLog(f"Laravel scheduler genel hata: {e}")
            return False


