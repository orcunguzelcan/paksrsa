import schedule
import time
import os
import shutil
import psutil
from Logger import LOGGER
import fingerprint_config as fpconfig

import database_config as dbconfig
import paks_database
from datetime import datetime, timedelta as td
import threading
import video_stream
import cv2
import subprocess
import ftplib

fingerprint_check_lock = fpconfig.fingerprint_check_lock
dev = fpconfig.dev


class RoutineJobs:

    def __init__(self):
        print("initializing routinejobs")
        self.mode = 0o777
        self.rootFile = "FTP"
        self.sourcePhotos = "C:/PAKS-STORAGE/Photos"
        self.config_file = "config.txt"  # Config dosya yolu
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
        while True:
            schedule.run_pending()
            time.sleep(1)

    def getPath(self):
        if not os.path.exists(self.rootFile):
            os.makedirs(self.rootFile, mode=0o777)

    # --- Config dosyasından veri okuma ---
    def get_config_value(self, target_key):
        """config.txt dosyasından istenen anahtarın değerini okur."""
        try:
            if not os.path.exists(self.config_file):
                LOGGER.WriteLog(f"Config dosyası bulunamadı: {self.config_file}")
                return None

            with open(self.config_file, "r", encoding="utf-8") as file:
                for line in file:
                    if "=" in line:
                        key, value = line.split("=", 1)
                        if key.strip() == target_key:
                            return value.strip()
            return None
        except Exception as e:
            LOGGER.WriteLog(f"Config okuma hatası: {e}")
            return None

    # -------------------------------------------------------------

    def backup_mysql(self):
        try:
            backup_dir = os.path.join(self.rootFile, "db")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"mysql_backup_{timestamp}.sql")

            # --- DÜZELTME: Hardcoded şifreler kaldırıldı, dbconfig'den okunan veriler eklendi ---
            # Not: -p ile şifre arasında boşluk olmamalıdır.
            dump_cmd = f"mysqldump -u {dbconfig.Uid} -p{dbconfig.Password} {dbconfig.Database} > {backup_file}"

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
                destinationRoot = os.path.join(self.rootFile, BackupMode, str(dailyTime.year), str(dailyTime.month),
                                               str(dailyTime.day))

                if not destinationRoot == "":
                    os.makedirs(destinationRoot, exist_ok=True)
                    tempDestination = destinationRoot
                    path = Source
                    newPath = tempDestination
                    for item in os.listdir(path):
                        s = os.path.join(path, item)
                        d = os.path.join(newPath, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)

                    LOGGER.WriteLog(f"{BackupMode} yedekleme tamamlandı.")
            except subprocess.CalledProcessError as e:
                LOGGER.WriteLog(f"chmod command error: {e}")
            except Exception as e:
                LOGGER.WriteLog(f"Yedekleme sırasında hata oluştu:{e}")

    def FTPUpload(self):
        LOGGER.WriteLog("Dosyalar gönderiliyor...")

        # --- Config'den IP okuma ---
        ftp_host_ip = self.get_config_value("RemoteHost")

        if not ftp_host_ip:
            LOGGER.WriteLog("FTP Hatası: config.txt dosyasında 'RemoteHost' bulunamadı.")
            return

        ftp_host = ftp_host_ip
        # FTP şifreleri isteğiniz üzerine hardcoded olarak bırakıldı
        ftp_user = 'rsa'
        ftp_pass = 'qw34qw34'
        ftp_port = 21

        def ensure_ftp_directory(ftp, path):
            parts = path.replace("\\", "/").split("/")
            for part in parts:
                if not part:
                    continue
                try:
                    ftp.mkd(part)
                except ftplib.error_perm as e:
                    if not str(e).startswith("550"):
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
                        ensure_ftp_directory(ftp, relative_path)

                    for filename in files:
                        file_path = os.path.join(root, filename)
                        with open(file_path, "rb") as file:
                            ftp.storbinary(f'STOR {filename}', file)

                    if relative_path != ".":
                        ftp.cwd("..")

            LOGGER.WriteLog(f"Dosyalar gönderildi ({ftp_host})...")

            for item in os.listdir(self.rootFile):
                item_path = os.path.join(self.rootFile, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            LOGGER.WriteLog("Dosyalar silindi.")

        except Exception as e:
            LOGGER.WriteLog(f"FTP aktarımında hata oluştu: {e}")

    def RemoveOldPhotos(self):
        if (os.path.isdir(self.getPath())):
            # os.chmod(self.sourceDb, self.mode) # sourceDb kaldırıldığı için commentlendi
            FD = psutil.disk_usage('/')
            self.mDatabase.insertFDPercent(FD.percent)
            if FD.percent >= 95:
                oneYear = td(days=360) / td(days=1)
                deleteList = list()
                for root, directories, files in os.walk(self.sourcePhotos, topdown=False):
                    if FD.percent > 0:
                        for name in files:
                            diffFromNow = int(datetime.now().timestamp() - (os.path.getmtime(root)))
                            if diffFromNow > oneYear:
                                deleteList.append(os.path.join(root, name))
                        for name in directories:
                            diffFromNow = int(datetime.now().timestamp() - (os.path.getmtime(root)))
                            if diffFromNow > oneYear:
                                deleteList.append(os.path.join(root, name))
                    else:
                        break

                if len(deleteList) > 0:
                    LOGGER.WriteLog("1 yıldan önceki fotoğraflar silindi!")

                for i in deleteList:
                    if os.path.isfile(i):
                        os.remove(i)
                    elif os.path.isdir(i):
                        os.rmdir(i)

    def systemRestart(self):
        try:
            LOGGER.WriteLog("Servisler yeniden başlatıldı.")
            os.system("shutdown /r /t 0")
        except Exception as e:
            LOGGER.WriteLog("Error: " + str(e))

    def NTPSync(self):
        """
        Windows Time Service (w32time) kullanarak saati senkronize eder.
        IP'yi config.txt dosyasından okur.
        """
        try:
            # IP Adresini Config'den Okuma
            self.ntpServer = self.get_config_value("RemoteHost")

            if not self.ntpServer:
                LOGGER.WriteLog("NTP senkronizasyonu atlandı: config.txt dosyasında 'RemoteHost' yok.")
                return

            LOGGER.WriteLog(f"NTP senkronizasyonu başlatılıyor (Config): {self.ntpServer}")

            # 1. Windows Time servisini başlatmayı dene
            subprocess.run(
                "net start w32time",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # 2. NTP Sunucusunu ayarla
            config_command = (
                f'w32tm /config /manualpeerlist:"{self.ntpServer}" '
                f'/syncfromflags:manual /update'
            )
            subprocess.run(config_command, shell=True, check=True)

            # 3. Senkronizasyonu zorla
            sync_command = "w32tm /resync"
            subprocess.run(sync_command, shell=True, check=True)

            LOGGER.WriteLog("NTP update successful.")

        except subprocess.CalledProcessError as e:
            LOGGER.WriteLog(f"NTP Sync Command Failed: {e}")
        except Exception as e:
            LOGGER.WriteLog(f"NTP General Error: {e}")

    def checkUsage(self):
        ram = psutil.virtual_memory()
        ramUsage = round(ram.percent)
        cpuUsage = round(psutil.cpu_percent(interval=1))
        cpuTemperature = None
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        cpuTemperature = round(entries[0].current)
                        break
        if cpuTemperature is None:
            cpuTemperature = 0
        FD = psutil.disk_usage('C:\\')
        self.mDatabase.insertFDPercent(FD.percent)
        self.mDatabase.insertUsage(ramUsage, cpuUsage, cpuTemperature)

    def check_fingerprint_module(self, dev):
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

    def get_camera_health(self):
        try:
            if video_stream.camera_running and video_stream.current_frame is not None:
                return True
            else:
                LOGGER.WriteLog("Kamera sağlık kontrolü: Frame alınamıyor veya kamera kapalı.")
                return False
        except Exception as e:
            LOGGER.WriteLog(f"Kamera sağlık kontrolü hatası: {e}")
            return False

    def componentsHealths(self):
        global dev
        fp_sensor_health_result = 1 if self.check_fingerprint_module(dev) else 0
        camera_health_result = 1 if self.get_camera_health() else 0
        self.mDatabase.insertComponentsHealths(1, fp_sensor_health_result, camera_health_result)

    def checkCrimeStatus(self):
        self.mDatabase.updateCrimeStatus()

    def checkAbsent(self):
        self.mDatabase.updateAbsentPeopleBulk()
        LOGGER.WriteLog("Kaçaklar işaretlendi (Eski Yöntem).")

    def checkPassive(self):
        try:
            self.mDatabase.updatePassivePeopleBulk()
            LOGGER.WriteLog("Pasif durum kontrolü tamamlandı.")
        except Exception as e:
            LOGGER.WriteLog(f"checkPassive hatası: {e}")

    def runLaravelScheduler(self):
        try:
            # LOGGER.WriteLog("Laravel schedule:run komutu çalıştırılıyor...")
            project_path = 'C:\\paks'
            result = subprocess.run(
                ['php', 'artisan', 'schedule:run'],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                if output and "No scheduled commands are ready to run" not in output:
                    LOGGER.WriteLog(f"Laravel Scheduler Başarılı: {output}")
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