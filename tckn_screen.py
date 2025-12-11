import tkinter as tk
import threading
import time
import os
import cv2
from PIL import Image, ImageTk
import video_stream
import fingerprint_config as fpconfig
import sound_config
from Logger import LOGGER

# --- GLOBAL ÖNBELLEK ---
# Animasyonu her seferinde diskten okumamak için RAM'de tutacağız
animation_frames = []


def load_animation_to_memory(path, target_w, target_h):
    """
    Videoyu kare kare okur, yeniden boyutlandırır ve RAM'e kaydeder.
    VideoCapture hemen kapatılır, böylece ana kamera ile çakışmaz.
    """
    global animation_frames
    if len(animation_frames) > 0:
        return  # Zaten yüklü

    temp_cap = cv2.VideoCapture(path)
    if not temp_cap.isOpened():
        LOGGER.WriteLog(f"Animasyon dosyası açılamadı: {path}")
        return

    LOGGER.WriteLog(f"Animasyon belleğe yükleniyor... {path}")

    while True:
        ret, frame = temp_cap.read()
        if not ret:
            break

        # Renk dönüşümü ve boyutlandırma
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

        animation_frames.append(frame)

    temp_cap.release()  # <--- KRİTİK: Kaynağı hemen serbest bırak
    LOGGER.WriteLog(f"Animasyon yüklendi. Toplam kare: {len(animation_frames)}")


def start_scan_process(root_main):
    # Çift tıklama koruması
    try:
        if getattr(video_stream, 'fingerprint_thread_active', False):
            LOGGER.WriteLog("Tarama zaten aktif, mükerrer tıklama engellendi.")
            return
    except Exception:
        pass

    sound_config.play_sound(sound_config.soundNowFinger)
    video_stream.fingerprint_thread_active = True

    scan_window = tk.Toplevel()
    scan_window.attributes("-fullscreen", True)
    scan_window.title("Parmak İzi Tarama")
    scan_window.configure(bg="black")

    scan_window.state('normal')
    scan_window.lift()
    scan_window.focus_force()
    scan_window.grab_set()

    main_frame = tk.Frame(scan_window, bg="black")
    main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    left_frame = tk.Frame(main_frame, bg="black", width=512)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    right_frame = tk.Frame(main_frame, bg="black", width=512)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    video_label = tk.Label(left_frame, bg="black")
    video_label.pack(side=tk.TOP, expand=True)

    animation_label = tk.Label(right_frame, bg="black")
    animation_label.pack(side=tk.TOP, expand=True)

    info_label = tk.Label(
        scan_window,
        text="Parmak İzi Okutmak İçin Yeşil Işık Yanan Sensöre Dokunun",
        font=("Arial", 16, "bold"),
        fg="white",
        bg="#630e0e",
        pady=10
    )
    info_label.pack(side=tk.BOTTOM, fill=tk.X)

    scan_window.update_idletasks()
    scan_window.update()
    root_main.withdraw()

    # --- ANİMASYON HAZIRLIĞI ---
    TARGET_W = 480
    TARGET_H = 360

    # Dosya yolu bulma
    animation_path = None
    candidates = [
        os.path.join("PAKS_PHOTO", "animation.mp4"),
        os.path.join("PAKS-PHOTO", "animation.mp4"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            animation_path = candidate
            break

    # Eğer animasyon varsa ve bellekte yoksa yükle
    if animation_path:
        threading.Thread(target=load_animation_to_memory, args=(animation_path, TARGET_W, TARGET_H),
                         daemon=True).start()

    current_frame_index = 0

    def update_animation():
        nonlocal current_frame_index
        global animation_frames

        if not getattr(video_stream, 'fingerprint_thread_active', False):
            return
        if not animation_label.winfo_exists():
            return

        # Kareler henüz yüklenmediyse bekle
        if len(animation_frames) == 0:
            animation_label.after(100, update_animation)
            return

        try:
            # Döngüsel indeks
            idx = current_frame_index % len(animation_frames)
            frame_data = animation_frames[idx]

            img_pil = Image.fromarray(frame_data)
            imgtk = ImageTk.PhotoImage(image=img_pil)

            animation_label.configure(image=imgtk)
            animation_label.image = imgtk

            current_frame_index += 1

        except Exception as e:
            LOGGER.WriteLog(f"Animasyon hatası: {e}")
            return

        # 30 FPS ~ 33ms
        if getattr(video_stream, 'fingerprint_thread_active', False) and animation_label.winfo_exists():
            animation_label.after(33, update_animation)

    # --- KAPATMA FONKSİYONU ---
    def on_close(event=None):
        LOGGER.WriteLog("Tarama ekranı kapatılıyor (Timeout veya Manuel).")

        # 1. Thread durdurma işareti ver (Sensör thread'i bunu görünce kendisi kapanacak)
        video_stream.fingerprint_thread_active = False

        # DÜZELTME: fpconfig.cancel_scanning() KALDIRILDI.
        # Bu fonksiyon UI thread'inde çalışırken, sensör thread'i capture modundaysa
        # sürücü kilitleniyor (deadlock) ve UI donuyordu.
        # Artık UI, sensörü beklemeden hemen kapanacak.

        # 2. UI güncellemesini durdur
        video_stream.stop_ui_update()

        root_main.deiconify()
        root_main.state('normal')
        root_main.lift()
        root_main.update()

        try:
            scan_window.destroy()
        except:
            pass

    # --- DONANIMLARI BAŞLAT ---
    threading.Thread(target=video_stream.open_camera_in_label, args=(video_label,)).start()
    update_animation()

    # Timeout Dinleyicisi
    video_label.bind("<<Timeout>>", on_close)

    time.sleep(0.5)

    fp_thread = threading.Thread(target=fpconfig.find_finger_1_to_N, args=(scan_window, root_main))
    fp_thread.start()

    scan_window.protocol("WM_DELETE_WINDOW", on_close)
    scan_window.mainloop()