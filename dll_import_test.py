import pythonnet
pythonnet.load("netfx")
import clr
import os
import sys
import time
# Python dosyasının bulunduğu dizin
base_dir = os.path.dirname(os.path.abspath(__file__))

# Native DLL'in bulunduğu klasör (x64)
native_dll_dir = os.path.join(base_dir, "x64")

# PATH ortam değişkenine native DLL klasörünü ekle ki sistem bulabilsin
os.environ["PATH"] = native_dll_dir + os.pathsep + os.environ.get("PATH", "")

# CLR için DLL klasörüne, yani base_dir'e ekle
sys.path.append(base_dir)

# Bio.TrustFinger.dll'i yükle
clr.AddReference("Bio.TrustFinger")

from Aratek.TrustFinger import TrustFingerManager,TrustFingerDevice,LedStatus

# SDK'yı başlat
TrustFingerManager.GlobalInitialize()

# Cihaz sayısını al
dev_count = TrustFingerManager.GetDeviceCount()

dev = TrustFingerDevice()
dev.Open(0)

dev.SetLedStatus(1, LedStatus.Off)
print(f"Bağlı cihaz sayısı: {dev_count}")
time.sleep(5)

if dev_count > 0:
    dev = TrustFingerManager.GetDeviceDescription(0)
    print(f"Cihaz Modeli: {dev.ProductModel}")
    print(f"Seri Numarası: {dev.SerialNumber}")
else:
    print("Hiçbir cihaz bağlı değil.")
