import threading
import time

import mysql.connector
from mysql.connector import Error, pooling  # pooling eklendi

from Logger import LOGGER

import os
import database_config as dbconfig


def initialize_database_if_needed():
    """
    Veritabanı ve temel tabloları kontrol eder.
    Yoksa full.sql dosyasını çalıştırarak oluşturur.
    """
    # 1) Önce belirtilen veritabanında örnek bir tabloyu arıyoruz
    try:
        conn = mysql.connector.connect(
            host=dbconfig.Server,
            user=dbconfig.Uid,
            password=dbconfig.Password,
            database=dbconfig.Database,
        )
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'people'")
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result is not None:
            print("Veritabanı ve tablolar zaten mevcut, full.sql çalıştırılmadı.")
            return
    except Error as e:
        print("Veritabanı kontrolünde hata veya veritabanı yok:", e)

    # 2) Buraya geldiysek, ya veritabanı yok ya da kritik tablo eksik.
    print("full.sql çalıştırılıyor, veritabanı ve tablolar oluşturulacak...")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_sql_path = os.path.join(base_dir, "full.sql")

    if not os.path.exists(full_sql_path):
        print(f"full.sql dosyası bulunamadı: {full_sql_path}")
        return

    try:
        conn = mysql.connector.connect(
            host=dbconfig.Server,
            user=dbconfig.Uid,
            password=dbconfig.Password,
        )
        cursor = conn.cursor()

        with open(full_sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        statements = []
        statement = ""
        in_single_quote = False
        in_double_quote = False

        for ch in sql_script:
            if ch == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
            elif ch == '"' and not in_single_quote:
                in_double_quote = not in_double_quote

            if ch == ";" and not in_single_quote and not in_double_quote:
                if statement.strip():
                    statements.append(statement.strip())
                statement = ""
            else:
                statement += ch

        if statement.strip():
            statements.append(statement.strip())

        cleaned_statements = []
        for stmt in statements:
            lines = stmt.splitlines()
            new_lines = []
            for line in lines:
                stripped_line = line.lstrip()
                if stripped_line.startswith("--"):
                    continue
                if stripped_line == "":
                    continue
                new_lines.append(stripped_line)

            if not new_lines:
                continue

            cleaned_stmt = "\n".join(new_lines)
            cleaned_statements.append(cleaned_stmt)

        for stmt in cleaned_statements:
            try:
                cursor.execute(stmt)
            except Error as e:
                print("SQL komutu çalıştırılırken hata:", e)
                print("Problemli komut (kısaltılmış):", stmt[:120].replace("\n", " "))
                continue

        conn.commit()
        cursor.close()
        conn.close()
        print("full.sql başarıyla çalıştırıldı, veritabanı hazır.")
    except Error as e:
        print("full.sql çalıştırılırken MySQL hatası oluştu:", e)
    except Exception as e:
        print("full.sql çalıştırılırken genel hata oluştu:", e)


class PaksDatabase:

    def __init__(self, Server, Uid, Password, Database):
        self.Server = Server
        self.Uid = Uid
        self.Password = Password
        self.Database = Database
        self.QueryList = list()
        self.QueryListMutex = threading.Lock()

        # --- CONNECTION POOL OLUŞTURMA ---
        # Pool size 5-10 arası genelde kiosk sistemleri için yeterlidir.
        # Pool name unique olmalıdır.
        try:
            db_config = {
                "host": self.Server,
                "user": self.Uid,
                "password": self.Password,
                "database": self.Database
            }
            self.pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="paks_pool",
                pool_size=5,
                pool_reset_session=True,
                **db_config
            )
            LOGGER.WriteLog("PaksDatabase Connection Pool initialized")
        except Error as e:
            LOGGER.WriteLog(f"Error initializing connection pool: {e}")
            raise e

        self.ProcessThread = threading.Thread(target=self.Process)
        self.ProcessThread.start()
        LOGGER.WriteLog("PaksDatabase initialized")

    def dbConnect(self):
        """
        Havuzdan bir bağlantı nesnesi döndürür.
        """
        try:
            cnx = self.pool.get_connection()
            return cnx
        except Error as e:
            LOGGER.WriteLog(f"Error getting connection from pool: {e}")
            raise e

    def Process(self):
        while True:
            conn = None
            try:
                tempQuery = ""
                with self.QueryListMutex:
                    if len(self.QueryList) > 0:
                        tempQuery = self.QueryList.pop()

                # Eğer sorgu varsa havuzdan bağlantı alıp işletelim
                if len(tempQuery) > 0:
                    conn = self.dbConnect()
                    if not conn.is_connected():
                        # Çok nadir durumda pool'dan gelen kopuksa tekrar dene
                        conn.reconnect(attempts=3, delay=1)

                    myCursor = conn.cursor()
                    myCursor.execute(tempQuery)

                    # Process genellikle INSERT/UPDATE işlemleri için kullanılıyor
                    if not tempQuery.split(" ")[0].lower() == "select":
                        conn.commit()

                    # Cursor kapat
                    myCursor.close()

                time.sleep(0.1)  # Döngüyü çok az rahatlat (0.5 sn çok uzun olabilir, 0.1'e çektim)

            except Error as e:
                LOGGER.WriteLog(f"Process Loop SQL Error: {e}")
                time.sleep(2)  # Hata durumunda bekleme süresi
                continue
            except (IndexError, KeyError) as ie:
                print("Index not found in dictionary!", ie)
                break
            except Exception as e:
                LOGGER.WriteLog(f"Process Loop General Error: {e}")
            finally:
                # Bağlantıyı havuza iade et (Kritik!)
                if conn is not None and conn.is_connected():
                    conn.close()

    def Execute(self, tempQuery):
        conn = None
        myCursor = None
        try:
            conn = self.dbConnect()
            if not conn.is_connected():
                conn.reconnect(attempts=3, delay=1)

            # Log yoğunluğunu azaltmak için her bağlantıda log yazmayı kapatabiliriz
            # ama orijinal akışı bozmamak için bırakıyorum.
            # LOGGER.WriteLog("PaksDatabase Db Connected (Pool)")

            myCursor = conn.cursor()
            myCursor.execute(tempQuery)

            LOGGER.WriteLog(
                f"PaksDatabase {tempQuery[:100]}... executed")  # Query çok uzunsa logu şişirmesin diye kısalttım
            effectedRowCount = myCursor.rowcount

            result = []
            command_type = tempQuery.split(" ")[0].lower()

            if command_type != "select":
                conn.commit()

            if command_type == "select":
                result = myCursor.fetchall()

            return result, effectedRowCount

        except Error as e:
            print("Error while connecting or executing MySQL", e)
            LOGGER.WriteLog(f"Execute Error: {e}")
            return [], 0  # Hata durumunda boş dönmeli ki program çökmesin

        except (IndexError, KeyError) as ie:
            print("Index not found in dictionary!", ie)
            return [], 0

        finally:
            # İşlem bitince veya hata çıkınca cursor ve bağlantıyı temizle/havuza at
            if myCursor is not None:
                try:
                    myCursor.close()
                except:
                    pass
            if conn is not None and conn.is_connected():
                conn.close()  # Havuza iade eder
            # LOGGER.WriteLog("PaksDatabase Db Connection Returned to Pool..")

    # --- Diğer Fonksiyonlar (Mantıkları Değiştirilmedi) ---

    def selectFingerPrintsTable(self):
        selectInfoQuery = "SELECT * FROM finger_prints"
        result, effectedRows = self.Execute(selectInfoQuery)
        return result

    def select_person_fingerprints(self, person_id):
        selectInfoQuery = "SELECT * FROM finger_prints where person_id= " + str(person_id) + " and info is not null"
        result, effectedRows = self.Execute(selectInfoQuery)
        return result

    def selectInfo(self):
        selectInfoQuery = "SELECT info FROM finger_prints"
        result, effectedRows = self.Execute(selectInfoQuery)
        return result

    def selectTCNo(self, personResulInt):
        selectTCNoQuery = f"SELECT tc_no FROM people WHERE id='{str(personResulInt)}'"
        result, effectedRows = self.Execute(selectTCNoQuery)
        if result and len(result) > 0:
            return result[0][0]
        return None

    def selectBlackListTable(self):
        selectBlacklistPersonResultQuery = f"SELECT * FROM black_lists where deleted_at is null"
        result, effectedRows = self.Execute(selectBlacklistPersonResultQuery)
        return result

    def selectPersonCrimeCheckTimesTable(self, crime_id):
        selectCrimeCheckTimesResultQuery = f"SELECT * FROM crime_check_times where print_status is NULL and crime_id =" + str(
            crime_id) + " and start_time<=NOW() and end_time>=NOW() and deleted_at is NULL"
        result, effectedRows = self.Execute(selectCrimeCheckTimesResultQuery)
        return result

    def _normalize_image_path(self, imagePath):
        if imagePath is None:
            return None
        p = str(imagePath).strip()
        if p == "" or p.upper() == "NULL":
            return None
        p = p.replace("\\", "/")
        p = p.replace("'", "''")
        return p

    def selectCrimeResult(self, personResultInt):
        selectCrimeResultQuery = f"SELECT crimes.id FROM crimes WHERE status = '1' AND person_id = '{str(personResultInt)}' AND deleted_at is null"
        result, effectedRows = self.Execute(selectCrimeResultQuery)
        return result

    def selectCrimeCheckTimesTable(self):
        selectCrimeCheckTimesResultQuery = f"SELECT * FROM crime_check_times where deleted_at is NULL"
        result, effectedRows = self.Execute(selectCrimeCheckTimesResultQuery)
        return result

    def selectPersonCrimesTable(self, person_id):
        selectCrimesQuery = f"SELECT * FROM crimes where person_id=" + str(
            person_id) + " and status=1 and deleted_at is null"
        result, effectedRows = self.Execute(selectCrimesQuery)
        return result

    def selectPersonIdResult(self, index):
        selectPersonIdResultQuery = "SELECT person_id FROM finger_prints where id= " + str(index)
        result, effectedRows = self.Execute(selectPersonIdResultQuery)
        return result

    def selectPersonId(self, fingerId):
        selectPersonIdQuery = f"SELECT person_id FROM finger_prints WHERE id='{str(fingerId)}'"
        result, effectedRows = self.Execute(selectPersonIdQuery)
        if result and len(result) > 0:
            resultInt = result[0][0]
            return resultInt
        return None

    def selectPersonIdAndInfo(self):
        selectPersonIdAndInfoQuery = "SELECT distinct(person_id) FROM finger_prints where info is not null"
        result, effectedRows = self.Execute(selectPersonIdAndInfoQuery)
        return result

    def selectUsedPersonIdsForDetection(self, timeForSecond):
        selectPersonIdAndInfoQuery = f"SELECT DISTINCT person_id FROM black_list_detecteds WHERE time >= NOW() - INTERVAL {timeForSecond} SECOND"
        result, effectedRows = self.Execute(selectPersonIdAndInfoQuery)
        return result

    def selectPeopleTable(self):
        selectInfoQuery = "SELECT * FROM people where deleted_at is null"
        result, effectedRows = self.Execute(selectInfoQuery)
        return result

    def selectPeopleWithTCKN(self, tc_no):
        selectInfoQuery = "SELECT * FROM people where tc_no=" + tc_no + " and deleted_at is null"
        result, effectedRows = self.Execute(selectInfoQuery)
        return result

    def selectPersonResult(self, personIdInt):
        selectPersonResultQuery = f"SELECT id FROM people WHERE id='{str(personIdInt)}' AND deleted_at is null"
        result, effectedRows = self.Execute(selectPersonResultQuery)
        return result

    def selectPersonResultWithTckn(self, tckn):
        selectPersonResultQuery = f"SELECT id,UNIX_TIMESTAMP(CURRENT_TIMESTAMP()) as t_now,cct.id as crime_check_time_id,UNIX_TIMESTAMP(cct.start_time) as c_start_time,UNIX_TIMESTAMP(cct.end_time) c_end_time  FROM people p"
        selectPersonResultQuery += " inner join  crimes c on c.person_id=p.id"
        selectPersonResultQuery += " inner join crime_check_times cct on cct.crime_id=c.id"
        selectPersonResultQuery += f" where p.tc_no='{tckn}' AND p.deleted_at is null and c.deleted_at is null and cct.deleted_at is null"
        selectPersonResultQuery += " and c.status=1"

        result, effectedRows = self.Execute(selectPersonResultQuery)
        return result

    def selectBlacklistPersonResult(self, personResultInt):
        selectBlacklistPersonResultQuery = f"SELECT person_id FROM black_lists WHERE person_id='{str(personResultInt)}' and deleted_at is null"
        result, effectedRows = self.Execute(selectBlacklistPersonResultQuery)
        return result

    def insertBlacklist(self, personResultInt):
        insertBlacklistQuery = f"INSERT INTO black_list_detecteds(time,person_id) VALUES (NOW(),'{str(personResultInt)}')"
        self.QueryList.append(insertBlacklistQuery)

    def selectCrimesTable(self):
        selectCrimesQuery = f"SELECT * FROM crimes where deleted_at is null"
        result, effectedRows = self.Execute(selectCrimesQuery)
        return result

    def selectCrimesTableWithPersonId(self, personIDInt):
        selectCrimesQueryWithPersonId = f"SELECT id FROM crimes where deleted_at is null and status=1 and person_id = '{str(personIDInt)}'"
        result, effectedRows = self.Execute(selectCrimesQueryWithPersonId)
        return result

    def selectIdFromPersonCrimeCheckTimesTable(self, crime_id, day_check=False):
        if day_check:
            selectCrimeCheckTimesResultQuery = f"SELECT id FROM crime_check_times WHERE deleted_at is NULL and crime_id = '{str(crime_id)}' and ((date(start_time)<=CURRENT_DATE() or date(end_time)=CURRENT_DATE()) and deleted_at is NULL)"
        else:
            selectCrimeCheckTimesResultQuery = f"SELECT id FROM crime_check_times WHERE deleted_at is NULL and crime_id = '{str(crime_id)}' and start_time<=NOW() and end_time>=NOW() and deleted_at is NULL"
        result, effectedRows = self.Execute(selectCrimeCheckTimesResultQuery)
        return result

    def selectCrimeCheckTimesResult(self, crimeResult):
        selectCrimeCheckTimesResultQuery = f"SELECT * FROM crime_check_times WHERE deleted_at is NULL and crime_id = '{str(crimeResult)}' limit 1"
        result, effectedRows = self.Execute(selectCrimeCheckTimesResultQuery)
        return result

    def selectCrimeCheckTimesResultDay(self, crimeResult):
        selectCrimeCheckTimesResultDayQuery = f"SELECT * FROM crime_check_times WHERE deleted_at is NULL and crime_id = '{str(crimeResult)}' limit 1"
        result, effectedRows = self.Execute(selectCrimeCheckTimesResultDayQuery)
        return result

    def updateCrimeCheckTimes(self, printStatus, imagePath, crimeResult, crime_check_time_id=None):
        norm_path = self._normalize_image_path(imagePath)

        if printStatus == '1':
            if norm_path is not None:
                updateCrimeCheckTimesQuery = (
                    f"UPDATE crime_check_times "
                    f"SET print_status = '1', image_path = '{norm_path}', print_time = NOW() "
                    f"WHERE crime_id = '{str(crimeResult)}' "
                    f"AND print_status IS NULL AND start_time<=NOW() AND end_time>=NOW()"
                )
            else:
                updateCrimeCheckTimesQuery = (
                    f"UPDATE crime_check_times "
                    f"SET print_status = '1', image_path = NULL, print_time = NOW() "
                    f"WHERE crime_id = '{str(crimeResult)}' "
                    f"AND print_status IS NULL AND start_time<=NOW() AND end_time>=NOW()"
                )

        if printStatus == '3':
            if norm_path is not None:
                updateCrimeCheckTimesQuery = (
                    f"UPDATE crime_check_times "
                    f"SET print_status = '3', image_path = '{norm_path}', print_time = NOW() "
                    f"WHERE crime_id = '{str(crimeResult)}' "
                    f"AND print_status IS NULL "
                    f"AND (date(start_time)=CURRENT_DATE() OR date(end_time)=CURRENT_DATE())"
                )
            else:
                updateCrimeCheckTimesQuery = (
                    f"UPDATE crime_check_times "
                    f"SET print_status = '3', image_path = NULL, print_time = NOW() "
                    f"WHERE crime_id = '{str(crimeResult)}' "
                    f"AND print_status IS NULL "
                    f"AND (date(start_time)=CURRENT_DATE() OR date(end_time)=CURRENT_DATE())"
                )

        if crime_check_time_id is not None:
            updateCrimeCheckTimesQuery += " and id=" + str(crime_check_time_id)

        result, effectedRows = self.Execute(updateCrimeCheckTimesQuery)
        print("result: ", result, effectedRows)
        return effectedRows

    def insert_person(self, full_name, tc_no):
        full_name = full_name.replace("'", "''")
        tc_no = tc_no.replace("'", "''")

        insert_query = (
            "INSERT INTO people (full_name, tc_no, created_at, updated_at) "
            f"VALUES ('{full_name}', '{tc_no}', NOW(), NOW())"
        )

        result, affected_rows = self.Execute(insert_query)
        return affected_rows > 0

    def selectAllPersonResults(self):
        selectAllPersonResultsQuery = "SELECT id FROM people WHERE deleted_at is null"
        result, effectedRows = self.Execute(selectAllPersonResultsQuery)
        return result

    def insert_person_fingerprint(self, person_id, info):
        info = info.replace("'", "''")
        insert_query = (
            "INSERT INTO finger_prints (person_id, info, status, created_at, updated_at) "
            f"VALUES ({person_id}, '{info}', 1, NOW(), NOW())"
        )
        result, affected_rows = self.Execute(insert_query)
        return affected_rows > 0

    def insertUsage(self, ramUsage, cpuUsage, cpuTemperature):
        ramUsageQuery = f"INSERT INTO healths(name,status, check_time) VALUES('ram','{ramUsage}',NOW()) ON DUPLICATE KEY UPDATE status = '{ramUsage}', check_time=NOW()"
        cpuUsageQuery = f"INSERT INTO healths(name,status, check_time) VALUES('cpu_usage','{cpuUsage}',NOW()) ON DUPLICATE KEY UPDATE status = '{cpuUsage}', check_time=NOW()"
        cpuTempatureQuery = f"INSERT INTO healths(name,status, check_time) VALUES('cpu_temp','{cpuTemperature}',NOW()) ON DUPLICATE KEY UPDATE status = '{cpuTemperature}', check_time=NOW()"

        self.QueryList.append(ramUsageQuery)
        self.QueryList.append(cpuUsageQuery)
        self.QueryList.append(cpuTempatureQuery)

    def insertFDPercent(self, fdPercent):
        fdPercentQuery = f"INSERT INTO healths(name,status, check_time) VALUES('storage','{int(fdPercent)}',NOW()) ON DUPLICATE KEY UPDATE status='{int(fdPercent)}',check_time=NOW()"
        self.QueryList.append(fdPercentQuery)

    def insertComponentsHealths(self, usSensorStatus, fpSensorStatus, cameraStatus):

        usSensorStatusQuery = f"INSERT INTO healths(name,status, check_time) VALUES('us_sensor','{usSensorStatus}',NOW()) ON DUPLICATE KEY UPDATE status = '{usSensorStatus}', check_time=NOW()"
        self.QueryList.append(usSensorStatusQuery)

        fpSensorStatusQuery = f"INSERT INTO healths(name,status, check_time) VALUES('fp_sensor','{fpSensorStatus}',NOW()) ON DUPLICATE KEY UPDATE status = '{fpSensorStatus}', check_time=NOW()"
        self.QueryList.append(fpSensorStatusQuery)

        cameraStatusQuery = f"INSERT INTO healths(name,status, check_time) VALUES('camera','{cameraStatus}',NOW()) ON DUPLICATE KEY UPDATE status = '{cameraStatus}', check_time=NOW()"
        self.QueryList.append(cameraStatusQuery)

    def getAbsentPeople(self):
        selectAbsentPeopleQuery = f"select p.full_name, p.tc_no, c.name from crime_check_times cct" \
                                  f" inner join crimes c on cct.crime_id=c.id" \
                                  f" inner join people p on p.id=c.person_id" \
                                  f" where cct.print_status is null and date(cct.end_time)<CURRENT_DATE() and cct.deleted_at is null" \
                                  f" and c.deleted_at is null" \
                                  f" and p.deleted_at is null order by cct.end_time"
        result, effectedRows = self.Execute(selectAbsentPeopleQuery)
        return result

    def selectAllCrimesForPerson(self, personId):
        selectAllCrimesForPersonQuery = f"SELECT id FROM crimes where deleted_at is null and person_id = '{personId}' and status = 1"
        result, effectedRows = self.Execute(selectAllCrimesForPersonQuery)
        return result

    def selectAllPassiveCrimesForPerson(self, personId):
        selectAllPassiveCrimesForPersonQuery = f"SELECT id FROM crimes where deleted_at is null and person_id = '{personId}' and status = 0"
        result, effectedRows = self.Execute(selectAllPassiveCrimesForPersonQuery)
        return result

    def selectAbsentPeople(self, crimeId):
        selectAbsentPeopleQuery = f"SELECT id FROM crime_check_times where deleted_at is null and crime_id = {crimeId} and print_status is null and date(end_time) < CURRENT_DATE() LIMIT 1"  #
        result, effectedRows = self.Execute(selectAbsentPeopleQuery)
        return result

    def updateAbsentPeople(self, crimeChecktimeId):
        updateAbsentPeopleQuery = f"update crime_check_times set print_status = '0' where id = {crimeChecktimeId} and print_status is null and date(end_time) < CURRENT_DATE()"
        self.QueryList.append(updateAbsentPeopleQuery)

    def updatePassivePeople(self, crimeChecktimeId):
        updatePassivePeopleQuery = f"update crime_check_times set print_status = '5' where id = {crimeChecktimeId} and print_status is null and date(end_time) < CURRENT_DATE()"
        self.QueryList.append(updatePassivePeopleQuery)

    def updateCrimeStatus(self):
        updateCrimeStatusQuery = f"update crimes set status=0 where date(end_time) < CURRENT_DATE()"
        self.QueryList.append(updateCrimeStatusQuery)

    def updateExpiredCrimesAndPrintStatus(self):
        updateCrimesQuery = """
        UPDATE crimes
        SET status = '0'
        WHERE status = '1'
          AND end_time < CURRENT_DATE()
        """
        self.Execute(updateCrimesQuery)

        updateQuery = """
        UPDATE crime_check_times cct
        INNER JOIN crimes c ON cct.crime_id = c.id
        SET cct.print_status = '5'
        WHERE c.status = '0'
          AND cct.print_status IS NULL
          AND DATE(cct.end_time) < CURRENT_DATE()
        """
        result, effectedRows = self.Execute(updateQuery)

        if effectedRows > 0:
            LOGGER.WriteLog(f"Toplam {effectedRows} adet pasif kayıt güncellendi.")

    def get_ntpserver(self):
        query = "SELECT ip FROM ntpserver LIMIT 1"
        result, rows = self.Execute(query)
        return result

    def insert_ntpserver(self, ip):
        query = f"INSERT INTO ntpserver(ip) VALUES('{ip}')"
        self.QueryList.append(query)

    def update_ntpserver(self, ip):
        query = f"UPDATE ntpserver SET ip='{ip}'"
        self.QueryList.append(query)

    def updateAbsentPeopleBulk(self):
        query = """
            UPDATE crime_check_times cct
            INNER JOIN crimes c ON cct.crime_id = c.id
            SET cct.print_status = '0'
            WHERE cct.print_status IS NULL
              AND cct.deleted_at IS NULL
              AND c.deleted_at IS NULL
              AND c.status = '1'
              AND DATE(cct.end_time) < CURRENT_DATE()
        """
        self.QueryList.append(query.strip())

    def updatePassivePeopleBulk(self):
        query = """
            UPDATE crime_check_times cct
            INNER JOIN crimes c ON cct.crime_id = c.id
            SET cct.print_status = '5'
            WHERE cct.print_status IS NULL
              AND cct.deleted_at IS NULL
              AND c.deleted_at IS NULL
              AND c.status = '0'
              AND DATE(cct.end_time) < CURRENT_DATE()
        """
        self.QueryList.append(query.strip())