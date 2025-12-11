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


def start_scan_process(root_main):
    """
    Kamera ve Tarama Ekranı.
    Timeout (Zaman Aşımı) desteği + yan tarafta animation.mp4 oynatma.
    """

    # --- DÜZELTME: Hata Kontrollü Çift Tıklama Koruması ---
    try:
        if getattr(video_stream, 'fingerprint_thread_active', False):
            LOGGER.WriteLog("Tarama zaten aktif, mükerrer tıklama engellendi.")
            return
    except Exception:
        # Eğer değişken yoksa veya hata olursa devam et (kilitlenme olmasın)
        pass
    # ---------------------------------------

    sound_config.play_sound(sound_config.soundNowFinger)
    video_stream.fingerprint_thread_active = True

    scan_window = tk.Toplevel()
    scan_window.attributes("-fullscreen", True)  # TAM EKRAN AÇ
    scan_window.title("Parmak İzi Tarama")
    scan_window.configure(bg="black")

    scan_window.state('normal')
    scan_window.lift()
    scan_window.focus_force()
    scan_window.grab_set()

    # --- ANA YAPI: Üstte kamera + animasyon, altta bilgi yazısı ---
    # Üst kısım (ekranın büyük bölümü)
    main_frame = tk.Frame(scan_window, bg="black")
    main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    # Sol tarafta canlı kamera
    left_frame = tk.Frame(main_frame, bg="black", width=512)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Sağ tarafta animation.mp4
    right_frame = tk.Frame(main_frame, bg="black", width=512)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    # Sabit boyutlu görüntü için sadece ortalanmış label
    video_label = tk.Label(left_frame, bg="black")
    video_label.pack(side=tk.TOP, expand=True)  # fill=BOTH YOK

    animation_label = tk.Label(right_frame, bg="black")
    animation_label.pack(side=tk.TOP, expand=True)  # fill=BOTH YOK

    # Alt kısım: bilgi yazısı (ekranın altında tek satır)
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

    # --- ANİMASYON VİDEOSU AYARLARI ---
    # Önce PAKS_PHOTO/animation.mp4, yoksa PAKS-PHOTO/animation.mp4 dene
    animation_path = None
    candidates = [
        os.path.join("PAKS_PHOTO", "animation.mp4"),
        os.path.join("PAKS-PHOTO", "animation.mp4"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            animation_path = candidate
            break

    anim_cap = None
    if animation_path is not None:
        try:
            anim_cap = cv2.VideoCapture(animation_path)
            if not anim_cap.isOpened():
                LOGGER.WriteLog(f"animation.mp4 açılamadı: {animation_path}")
                anim_cap = None
            else:
                LOGGER.WriteLog(f"animation.mp4 oynatılıyor: {animation_path}")
        except Exception as e:
            LOGGER.WriteLog(f"animation.mp4 açılırken hata: {e}")
            anim_cap = None
    else:
        LOGGER.WriteLog("animation.mp4 bulunamadı (PAKS_PHOTO / PAKS-PHOTO).")

    # Sabit boyutlar (kamera ile uyumlu dursun diye aynı kullanıyoruz)
    TARGET_W = 480
    TARGET_H = 360

    def update_animation():
        nonlocal anim_cap
        # Tarama bitti ise veya pencere kapandıysa döngüyü durdur
        if not getattr(video_stream, 'fingerprint_thread_active', False):
            return
        if not animation_label.winfo_exists():
            return
        if anim_cap is None:
            return

        try:
            ret, frame = anim_cap.read()
            if not ret:
                # Video bitti, başa sar
                anim_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = anim_cap.read()
                if not ret:
                    return

            # BGR -> RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Sabit boyut
            frame = cv2.resize(
                frame,
                (TARGET_W, TARGET_H),
                interpolation=cv2.INTER_AREA
            )

            img_pil = Image.fromarray(frame)
            imgtk = ImageTk.PhotoImage(image=img_pil)
            animation_label.configure(image=imgtk)
            animation_label.image = imgtk

        except Exception as e:
            LOGGER.WriteLog(f"Animasyon frame güncelleme hatası: {e}")
            return

        # ~30 FPS için 33 ms
        if getattr(video_stream, 'fingerprint_thread_active', False) and animation_label.winfo_exists():
            animation_label.after(33, update_animation)

    # --- KAPATMA FONKSİYONU ---
    def on_close(event=None):
        """Pencereyi kapatır ve ana ekrana döner."""
        nonlocal anim_cap
        LOGGER.WriteLog("Tarama ekranı kapatılıyor (Timeout veya Manuel).")

        # Tarama bittiği için kilidi kaldırıyoruz
        video_stream.fingerprint_thread_active = False

        # Animasyon videosunu serbest bırak
        try:
            if anim_cap is not None:
                anim_cap.release()
                anim_cap = None
        except Exception:
            pass

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

    # Animasyon döngüsünü başlat
    if anim_cap is not None:
        update_animation()

    # --- TIMEOUT DİNLEYİCİSİ ---
    video_label.bind("<<Timeout>>", on_close)
    # ----------------------------------

    time.sleep(0.5)
    fp_thread = threading.Thread(target=fpconfig.find_finger_1_to_N, args=(scan_window, root_main))
    fp_thread.start()

    scan_window.protocol("WM_DELETE_WINDOW", on_close)
    scan_window.mainloop()
