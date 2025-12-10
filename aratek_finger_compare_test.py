import pythonnet
pythonnet.load("netfx")
import clr
import os
import sys
import System


# Yolları ayarla
base_dir = os.path.dirname(os.path.abspath(__file__))
native_dll_dir = os.path.join(base_dir, "x64")
os.environ["PATH"] = native_dll_dir + os.pathsep + os.environ.get("PATH", "")
sys.path.append(base_dir)

clr.AddReference("Bio.TrustFinger")
from Aratek.TrustFinger import (
    TrustFingerManager, TrustFingerDevice,
    FingerPosition
)
# SDK'yı başlat
TrustFingerManager.GlobalInitialize()

# Cihaz bağlandı mı?
#device_count = TrustFingerManager.GetDeviceCount()
#if device_count == 0:
#    print("Hiçbir cihaz bağlı değil.")
#    sys.exit()

# Cihazı aç
dev = TrustFingerDevice()
dev.Open(0)

# Parmak izi al
print("Parmağınızı okutun...")
# 1. Parmak izini okut (bitmap çek)
while True:
    bmp_data = dev.CaptureBitmapData(5)
    if bmp_data and bmp_data.FingerprintImageData:  # Boş gelmezse
        break
    print("Parmak algılanamadı, tekrar deneyin...")

feature = dev.ExtractFeature(FingerPosition.UnKnow)
live_template = feature.FeatureData

# Kaydedilmiş template dosyasını oku
stored_path = os.path.join(base_dir, "stored_right_thumb.bione")
if not os.path.exists(stored_path):
    print(f"Template dosyası bulunamadı: {stored_path}")
    sys.exit()

with open(stored_path, "rb") as f:
    stored_bytes = f.read()

if len(stored_bytes) != 512:
    print("Hatalı template dosyası! 512 byte olmalı.")
    sys.exit()

stored_template = System.Array[System.Byte](list(stored_bytes))

# Doğrulama
level = 3
result = dev.Verify(level, live_template, stored_template)

# Sonuç
print("Doğrulama sonucu:")
print("- Eşleşme:", "✅ Evet" if result.get_IsMatch() else "❌ Hayır")
print("- Benzerlik skoru:", result.get_Similarity())
