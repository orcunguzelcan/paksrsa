import pythonnet

pythonnet.load("netfx")
import clr
import os
import sys
import System
import binascii
import time

# --- Yolları ve DLL Ayarlarını Yapılandır ---
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

import paks_database
import database_config as dbconfig

native_dll_dir = os.path.join(base_dir, "x64")
os.environ["PATH"] = native_dll_dir + os.pathsep + os.environ.get("PATH", "")

clr.AddReference("Bio.TrustFinger")
# LedStatus'u ekledik
from Aratek.TrustFinger import (
    TrustFingerManager, TrustFingerDevice,
    FingerPosition, LedStatus
)


def main():
    # 1. Veritabanı Bağlantısı
    print("--- Veritabanı Bağlanıyor ---")
    try:
        db = paks_database.PaksDatabase(dbconfig.Server, dbconfig.Uid, dbconfig.Password, dbconfig.Database)
        fingerprint_list = db.selectFingerPrintsTable()
        print(f"✅ Toplam {len(fingerprint_list)} kayıt çekildi.")
    except Exception as e:
        print(f"❌ DB Hatası: {e}")
        sys.exit()

    # 2. SDK Başlatma
    try:
        TrustFingerManager.GlobalInitialize()
        dev = TrustFingerDevice()
        dev.Open(0)
        print("✅ Parmak izi okuyucu açıldı.")
    except Exception as e:
        print(f"❌ Cihaz Hatası: {e}")
        sys.exit()

    # 3. Canlı Parmak İzi Alma
    print("\n💡 LED Yakılıyor ve Parmak Bekleniyor...")

    # YEŞİL IŞIĞI YAK (Index 0 = Yeşil, Index 1 = Kırmızı)
    try:
        dev.SetLedStatus(0, LedStatus.On)
    except Exception as e:
        print(f"LED Yakılamadı: {e}")

    while True:
        # Timeout süresini kısa tutuyoruz ki döngü hızlı dönsün
        bmp_data = dev.CaptureBitmapData(5)
        if bmp_data and bmp_data.FingerprintImageData:
            break
        time.sleep(0.1)

    # IŞIĞI SÖNDÜR (Okuma bitti)
    try:
        dev.SetLedStatus(0, LedStatus.Off)
    except:
        pass

    feature = dev.ExtractFeature(FingerPosition.UnKnow)
    if feature is None or feature.FeatureData is None:
        print("❌ Özellik çıkarılamadı!")
        sys.exit()

    live_template = feature.FeatureData
    live_len = len(live_template)
    print(f"\n🔵 OKUNAN PARMAK İZİ BOYUTU: {live_len} byte")

    if live_len == 0:
        print("❌ Hata: Okunan veri boş!")
        sys.exit()

    print("\n--- Karşılaştırma Başlıyor ---")

    match_found = False

    # 4. Güvenli Döngü
    for row in fingerprint_list:
        db_id = row[0]

        raw_hex_data = None
        if len(str(row[1])) > 100:
            raw_hex_data = row[1]
        elif len(row) > 2 and len(str(row[2])) > 100:
            raw_hex_data = row[2]

        if raw_hex_data is None:
            continue

        try:
            clean_hex = str(raw_hex_data).replace("'", "").replace("\n", "").strip()
            byte_data = binascii.unhexlify(clean_hex)
            stored_len = len(byte_data)

            # --- KRİTİK KONTROLLER ---
            if stored_len < 512:
                # Veri çok küçükse sessizce geç
                continue

            if stored_len != live_len:
                # Boyut uyuşmazlığı varsa sessizce geç (Log kirliliğini azaltmak için print'i kapattım)
                continue

            stored_template = System.Array[System.Byte](list(byte_data))

            # Eşleştirme (Level 3)
            result = dev.Verify(3, live_template, stored_template)

            if result.get_IsMatch():
                print(f"✅✅✅ EŞLEŞME BULUNDU! ID: {db_id} - Skor: {result.get_Similarity()}")

                # Kişiyi bul
                try:
                    person_id = db.selectPersonId(db_id)
                    print(f"     -> Person ID: {person_id}")
                except:
                    pass

                match_found = True
                # break # İsterseniz ilk bulduğunda durdurabilirsiniz

        except Exception as e:
            continue

    if not match_found:
        print("\n❌ Eşleşme bulunamadı.")
    else:
        print("\n✅ Tarama tamamlandı.")


if __name__ == "__main__":
    main()