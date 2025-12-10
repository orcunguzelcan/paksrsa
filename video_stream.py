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


def start_camera_service():
    """Kamerayı arka planda başlatır."""
    global camera_running
    if camera_running:
        return

    camera_thread = threading.Thread(target=_camera_worker, daemon=True)
    camera_thread.start()


def _camera_worker():
    """Sürekli okuma yapan işçi thread."""
    global current_frame, display_frame, camera_running

    cap = cv2.VideoCapture(0)

    # Kamera açılana kadar dene
    retry_count = 0
    while not cap.isOpened():
        time.sleep(1)
        cap = cv2.VideoCapture(0)
        retry_count += 1
        if retry_count > 10:
            LOGGER.WriteLog("Kamera donanımı başlatılamadı!")
            return

    camera_running = True
    LOGGER.WriteLog("Kamera servisi başladı.")

    while True:
        try:
            ret, frame = cap.read()
            if ret:
                # 1. Görüntüyü çevir (Dik ekran için)
                rotated_frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

                # 2. Üzerine tarih/saat yaz (BGR formatındayken)
                cv2.putText(rotated_frame,
                            str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                            (5, 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (255, 255, 255), 2, cv2.LINE_AA, False)

                # 3. UI için RGB'ye çevir (OpenCV BGR kullanır, Pillow RGB)
                rgb_frame = cv2.cvtColor(rotated_frame, cv2.COLOR_BGR2RGB)

                # 4. Global değişkenleri güncelle (KİLİT ALTINDA)
                with camera_lock:
                    current_frame = rotated_frame.copy()  # İşlemler için ham veri
                    display_frame = rgb_frame  # UI için hazır veri

            else:
                # Frame alınamazsa az bekle (CPU'yu yorma)
                time.sleep(0.1)

        except Exception as e:
            LOGGER.WriteLog(f"Kamera hatası: {e}")
            time.sleep(1)


def open_camera_in_label(target_label):
    """
    Görüntüyü Label'a basar.
    Thread-Safe ve Widget Varoluş Kontrollü Sürüm.
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
            except Exception as e:
                pass
            ui_update_active = False
            return

        # 3. Veriyi Güvenli Kopyalama (Thread Safety için Kritik Nokta)
        local_image_data = None

        # Sadece kopyalama işlemi sırasında kilitliyoruz.
        # Bu, UI thread'inin kamera thread'ini bloklamasını engeller.
        if camera_running:
            with camera_lock:
                if display_frame is not None:
                    # Derin kopya almaya gerek yok, numpy array kopyası yeterli
                    local_image_data = display_frame.copy()

        # 4. Görüntüyü UI'a Basma (Kilit dışı işlem)
        if local_image_data is not None:
            try:
                # Pillow Image oluşturma işlemi biraz maliyetlidir, bunu kilit dışında yapıyoruz
                img_pil = Image.fromarray(local_image_data)
                imgtk = ImageTk.PhotoImage(image=img_pil)

                # Sadece widget hala hayattaysa güncelle
                if target_label.winfo_exists():
                    target_label.configure(image=imgtk)
                    # Çöp toplayıcı (GC) resmi silmesin diye referans tutuyoruz:
                    target_label.image = imgtk
            except Exception as e:
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