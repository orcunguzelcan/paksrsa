import tkinter as tk
import cv2
import datetime
from PIL import Image, ImageTk
import threading
from Logger import LOGGER
import time
import numpy as np

# --- AYARLAR ---
resolution = (320, 240)
stream_timeout_seconds = 10

# Sabit gösterim boyutu (7" 1024x600 için uygun)
TARGET_W = 480
TARGET_H = 360

# --- DEĞİŞKENLER ---
# current_frame: Kameradan gelen ham (BGR) veri
current_frame = None
# display_frame: UI için hazırlanmış (RGB) ve döndürülmüş veri
display_frame = None

camera_running = False
ui_update_active = False

# Thread senkronizasyonu için kilit
camera_lock = threading.Lock()

# Parmak izi tarama bayrağı
fingerprint_thread_active = False

cap = None
import cv2
import time
from Logger import LOGGER


def reset_camera_device():
    """
    Uygulama her açıldığında kamerayı kısa süreliğine açıp kapatarak
    önceki oturumdan kalan kilitlenmeleri temizlemeyi dener.
    """
    backends = []

    # Bazı OpenCV sürümlerinde CAP_DSHOW sabiti olmayabiliyor, o yüzden try:
    try:
        backends.append(cv2.CAP_DSHOW)
    except AttributeError:
        pass

    try:
        backends.append(cv2.CAP_MSMF)
    except AttributeError:
        pass

    # En son fallback
    backends.append(cv2.CAP_ANY)

    for backend in backends:
        cap = None
        try:
            cap = cv2.VideoCapture(0, backend)
        except TypeError:
            # Bazı sürümlerde backend parametresi yoksa bu şekilde deneyelim
            cap = cv2.VideoCapture(0)

        if not cap or not cap.isOpened():
            # Bu backend ile açamadı, sıradakine geç
            if cap:
                cap.release()
            continue

        LOGGER.WriteLog(f"Kamera reset denemesi: backend={backend}")

        # Birkaç kare okumayı dene (driver’ı uyandırmak için)
        for _ in range(3):
            ret, _ = cap.read()
            if not ret:
                time.sleep(0.1)
            else:
                break

        # Kısa bir bekleme ve ardından kapatma
        time.sleep(0.2)
        cap.release()
        LOGGER.WriteLog("Kamera reset işlemi başarılı.")
        return True

    LOGGER.WriteLog("Kamera reset işlemi başarısız: hiçbir backend ile açılamadı.")
    return False


def start_camera_service():
    """Kamerayı arka planda başlatır."""
    global camera_running
    # Bu fonksiyon birden fazla kez çağrılsa bile
    # aynı anda sadece bir thread başlasın
    if camera_running:
        return

    camera_running = True  # Thread başlamadan önce işaretle
    camera_thread = threading.Thread(target=_camera_worker, daemon=True)
    camera_thread.start()


def _camera_worker():
    global current_frame, display_frame, camera_running, cap

    retry_count = 0
    while True:
        if cap is None or not cap.isOpened():
            try:
                # MSMF yerine mümkünse DirectShow kullan
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            except Exception:
                cap = cv2.VideoCapture(0)

        if cap.isOpened():
            break

        time.sleep(1)
        retry_count += 1
        if retry_count > 10:
            LOGGER.WriteLog("Kamera donanımı başlatılamadı!")
            camera_running = False   # Başlatılamadı, tekrar denenebilir
            return

    LOGGER.WriteLog("Kamera servisi başladı.")

    while camera_running:
        try:
            ret, frame = cap.read()
            if not ret:
                # MSMF hataları genelde burada ret=False olarak gelir
                LOGGER.WriteLog("Kameradan frame alınamadı, tekrar denenecek.")
                # Eski bağlantıyı kapat, biraz bekle ve tekrar aç
                try:
                    cap.release()
                except:
                    pass
                cap = None
                time.sleep(1)
                continue

            rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

            cv2.putText(rotated_frame,
                        str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        (5, 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 2, cv2.LINE_AA, False)

            rgb_frame = cv2.cvtColor(rotated_frame, cv2.COLOR_BGR2RGB)

            with camera_lock:
                current_frame = rotated_frame.copy()
                display_frame = rgb_frame

        except Exception as e:
            LOGGER.WriteLog(f"Kamera hatası: {e}")
            time.sleep(1)

    # Döngüden çıkarken kamerayı mutlaka serbest bırak
    try:
        if cap is not None and cap.isOpened():
            cap.release()
    except:
        pass
    LOGGER.WriteLog("Kamera servisi durduruldu.")


def stop_camera_service():
    """Kamera thread'ini ve cihazı kapat."""
    global camera_running, cap
    camera_running = False
    try:
        if cap is not None and cap.isOpened():
            cap.release()
            cap = None
    except:
        pass


def open_camera_in_label(target_label):
    """
    Görüntüyü Label'a basar.
    Thread-Safe ve Widget Varoluş Kontrollü Sürüm.
    SABİT BOYUTLU (TARGET_W x TARGET_H) GÖSTERİM.
    """
    global ui_update_active, stream_timeout_seconds
    ui_update_active = True
    start_time = datetime.datetime.now()

    def update_ui():
        global ui_update_active

        # 1. Döngü ve Widget Kontrolü
        if not ui_update_active:
            return

        try:
            # Widget yoksa döngüyü kır
            if not target_label.winfo_exists():
                ui_update_active = False
                return
        except Exception:
            ui_update_active = False
            return

        # 2. Zaman Aşımı Kontrolü
        elapsed = (datetime.datetime.now() - start_time).total_seconds()
        if elapsed > stream_timeout_seconds:
            try:
                # Timeout event'ini tetikle
                if target_label.winfo_exists():
                    target_label.event_generate("<<Timeout>>")
            except Exception:
                pass
            ui_update_active = False
            return

        # 3. Veriyi Güvenli Kopyalama (Thread Safety için Kritik Nokta)
        local_image_data = None

        if camera_running:
            with camera_lock:
                if display_frame is not None:
                    # numpy array kopyası yeterli
                    local_image_data = display_frame.copy()

        # 4. Görüntüyü UI'a Basma (Kilit dışı işlem)
        if local_image_data is not None:
            try:
                img_pil = Image.fromarray(local_image_data)

                # Sabit boyut (artık label boyutuna göre büyümüyor)
                img_pil = img_pil.resize((TARGET_W, TARGET_H), Image.LANCZOS)

                imgtk = ImageTk.PhotoImage(image=img_pil)

                # Sadece widget hala hayattaysa güncelle
                if target_label.winfo_exists():
                    target_label.configure(image=imgtk)
                    # Çöp toplayıcı (GC) resmi silmesin diye referans tutuyoruz:
                    target_label.image = imgtk
            except Exception:
                # Resim oluşturma sırasında hata olursa (örn: pencere kapanırsa) yoksay
                pass

        # 5. Bir sonraki kare için planlama (20ms = ~50 FPS)
        if ui_update_active and target_label.winfo_exists():
            target_label.after(20, update_ui)

    # Döngüyü başlat
    update_ui()


def stop_ui_update():
    global ui_update_active
    ui_update_active = False


# Eski kod uyumluluğu için (Snapshot vb. fonksiyonlar frame değişkenini kullanıyor olabilir)
frame = None


def update_legacy_frame_reference():
    global frame, current_frame
    while True:
        with camera_lock:
            if current_frame is not None:
                try:
                    # Buradaki frame değişkeni diğer modüllerde (snapshot) kullanılıyor
                    frame = current_frame  # Zaten BGR formatında
                except:
                    pass
        time.sleep(0.1)


# Legacy desteğini başlat
threading.Thread(target=update_legacy_frame_reference, daemon=True).start()
