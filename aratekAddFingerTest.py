import pythonnet

pythonnet.load("netfx")
import clr
import os
import sys
import System
import binascii
import time
import datetime
import random

# --- Yolları Ayarla ---
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

import paks_database
import database_config as dbconfig

# --- SDK Ayarları ---
native_dll_dir = os.path.join(base_dir, "x64")
os.environ["PATH"] = native_dll_dir + os.pathsep + os.environ.get("PATH", "")

clr.AddReference("Bio.TrustFinger")
from Aratek.TrustFinger import (
    TrustFingerManager, TrustFingerDevice,
    FingerPosition, LedStatus
)


def get_valid_person_id(db):
    """
    Veritabanındaki people tablosundan rastgele GERÇEK bir ID çeker.
    Eğer hiç kimse yoksa, hatayı önlemek için otomatik bir dummy kişi oluşturur.
    """
    try:
        # Mevcut kişilerden birini seç (Silinmemiş olanlardan)
        # Sadece ID'yi alıyoruz
        select_query = "SELECT id FROM people WHERE deleted_at IS NULL LIMIT 1"
        result, _ = db.Execute(select_query)

        if result and len(result) > 0:
            found_id = result[0][0]
            print(f"✅ Mevcut Kişi Bulundu (ID: {found_id}) - Bu ID kullanılacak.")
            return found_id

        else:
            print("⚠️ Tabloda hiç kişi yok! Garbage veri için geçici bir kişi (Dummy Person) oluşturuluyor...")
            # Tabloda kimse yoksa Constraint hatası yememek için sahte bir kişi ekle
            # TCKN rastgele oluşturulmalı (Unique olabilir)
            dummy_tc = str(random.randint(10000000000, 99999999999))
            insert_person_query = f"INSERT INTO people (name, surname, tc_no, created_at) VALUES ('Garbage', 'User', '{dummy_tc}', NOW())"

            # Insert işlemi (Execute içinde commit var varsayıyoruz)
            _, count = db.Execute(insert_person_query)

            # Eklenen kişinin ID'sini al (Son eklenen)
            # MySQL için LAST_INSERT_ID() veya tekrar select yaparak
            id_query = f"SELECT id FROM people WHERE tc_no = '{dummy_tc}' LIMIT 1"
            res_id, _ = db.Execute(id_query)

            new_id = res_id[0][0]
            print(f"✅ Yeni Dummy Kişi Oluşturuldu (ID: {new_id})")
            return new_id

    except Exception as e:
        print(f"❌ Kişi ID'si alınırken hata: {e}")
        return None


def main():
    # 1. Veritabanı Bağlantısı
    print("--- Veritabanına Bağlanılıyor ---")
    try:
        db = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)
        print("✅ Veritabanı bağlantısı hazır.")
    except Exception as e:
        print(f"❌ DB Bağlantı Hatası: {e}")
        sys.exit()

    # 2. ÖNCE GEÇERLİ BİR PERSON ID BUL
    # Parmak izini okutmadan önce bunu halledelim ki boşuna okutmuş olmayalım.
    valid_person_id = get_valid_person_id(db)

    if valid_person_id is None:
        print("❌ HATA: Geçerli bir Person ID bulunamadı veya oluşturulamadı. İşlem iptal.")
        sys.exit()

    # 3. Sensör Başlatma
    try:
        TrustFingerManager.GlobalInitialize()
        dev = TrustFingerDevice()
        dev.Open(0)
        print("✅ Sensör başlatıldı.")
    except Exception as e:
        print(f"❌ Sensör Hatası: {e}")
        sys.exit()

    # 4. Parmak İzi Okuma
    print(f"\n💡 Lütfen parmağınızı sensöre koyun (Kişi ID: {valid_person_id} için)...")

    try:
        dev.SetLedStatus(0, LedStatus.On)
    except:
        pass

    captured_template = None
    start_time = time.time()

    while (time.time() - start_time) < 10:
        bmp_data = dev.CaptureBitmapData(5)
        if bmp_data and bmp_data.FingerprintImageData:
            print("👌 Parmak algılandı...")
            feature = dev.ExtractFeature(FingerPosition.UnKnow)
            if feature and feature.FeatureData:
                captured_template = feature.FeatureData
                break
        time.sleep(0.1)

    try:
        dev.SetLedStatus(0, LedStatus.Off)
    except:
        pass

    if captured_template is None:
        print("❌ Parmak okunamadı.")
        sys.exit()

    # 5. Veritabanına Kayıt
    try:
        # Hex Dönüşümü
        template_bytes = bytes(list(captured_template))
        info_hex = binascii.hexlify(template_bytes).decode('utf-8')

        status = 1
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print(f"\n📝 Kayıt Başlıyor...")

        insert_query = f"""
            INSERT INTO finger_prints (person_id, info, status, created_at, updated_at)
            VALUES ('{valid_person_id}', '{info_hex}', '{status}', '{now_str}', '{now_str}')
        """

        # Execute sonucunu güvenli şekilde al
        result_tuple = db.Execute(insert_query)

        # Tuple unpack hatasını önlemek için kontrol
        if result_tuple:
            result, effected_rows = result_tuple
            if effected_rows > 0:
                print(f"✅✅✅ BAŞARILI: Parmak izi 'person_id: {valid_person_id}' üzerine kaydedildi.")
            else:
                print("⚠️ Sorgu çalıştı ama satır eklenmedi.")
        else:
            print("❌ Hata: Veritabanı sorgusu başarısız oldu (None döndü).")

    except Exception as e:
        print(f"\n❌ Kayıt Hatası: {e}")


if __name__ == "__main__":
    main()