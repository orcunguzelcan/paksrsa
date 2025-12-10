import tkinter as tk
from tkinter import messagebox
import cv2
import datetime
from PIL import Image, ImageTk
import threading
from Logger import LOGGER
import sound_config
import time  # get_camera_instance() içinde time.sleep kullanılıyor

#resolution = (800, 480)
resolution = (320, 240)
framerate = 30
frame = None
fingerprint_thread_active = False
camera = None
stream_timeout_seconds = 20
first_call_begin = datetime.datetime.now()
camera_lock = threading.Lock()  # Kamera erişimi için bir kilit


def get_camera_instance():
    global camera, camera_lock
    with camera_lock:  # Kilitleyerek erişimi güvenli hale getir
        retries = 5
        attempt = 0
        while attempt < retries:
            if camera is None or not camera.isOpened():
                camera = cv2.VideoCapture(0)
                if camera.isOpened():
                    return camera
            attempt += 1
            LOGGER.WriteLog(f"Kamera açılamadı, {attempt}. deneme...")
            time.sleep(1)

        return None


def open_camera(root):
    global first_call_begin, stream_timeout_seconds, camera, frame, fingerprint_thread_active
    fingerprint_thread_active = True
    first_call_begin = datetime.datetime.now()
    # Kamerayı başlat
    camera = get_camera_instance()  # cv2.VideoCapture(-1)  # 0, varsayılan kamera

    if camera is None or not camera.isOpened():
        print("Kamera açılamadı!")
        return

    camera_window = tk.Toplevel(root)
    camera_window.attributes("-fullscreen", True)
    camera_window.resizable(False, False)
    camera_window.title("Kamera Görüntüsü")
    # camera_window.geometry("800x480")
    camera_window.geometry("1024x600")
    # Ana çerçeve
    main_frame = tk.Frame(camera_window)
    main_frame.pack(fill=tk.BOTH, expand=True)
    # Sol tarafta görüntü için bir çerçeve
    video_frame = tk.Frame(main_frame, width=768, height=600)
    # video_frame = tk.Frame(main_frame, width=600, height=480)
    video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    video_label = tk.Label(video_frame)
    video_label.pack(expand=True, fill=tk.BOTH)

    # Sağ tarafta butonlar için bir çerçeve
    button_frame = tk.Frame(main_frame, width=256, height=600, bg="lightgray")
    # button_frame = tk.Frame(main_frame, width=200, height=480, bg="lightgray")
    button_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=0, pady=0)
    button_frame.pack_propagate(False)

    sound_config.play_sound(sound_config.soundNowFinger)

    def update_frame():
        global camera_lock, first_call_begin, stream_timeout_seconds, frame, fingerprint_thread_active
        camera_window.lift()
        try:
            if (datetime.datetime.now() - first_call_begin).total_seconds() > stream_timeout_seconds:
                cancel()
                return
            if not fingerprint_thread_active:
                cancel()
                return

            # --- KARE OKUMA & İŞLEME: LOKALDE YAP ---
            with camera_lock:
                ret, _raw = camera.read()
            if ret:
                local_bgr = cv2.rotate(_raw, cv2.ROTATE_90_COUNTERCLOCKWISE)
                cv2.putText(local_bgr,
                            str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                            (5, 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (255, 255, 255),
                            2,
                            cv2.LINE_AA,
                            False)
                local_rgb = cv2.cvtColor(local_bgr, cv2.COLOR_BGR2RGB)

                # --- GLOBAL 'frame' ATAMASINI KİLİT ALTINDA VE KOPYA OLARAK YAP ---
                with camera_lock:
                    # Diğer thread'lerin tutarlı bir kare görmesi için kopya ata
                    frame = local_rgb.copy()

                # Ekrana basılan görüntü, az önce ürettiğimiz lokal kopya
                img = Image.fromarray(local_rgb)
                imgtk = ImageTk.PhotoImage(img)
                video_label.imgtk = imgtk
                video_label.configure(image=imgtk)

            video_label.after(1, update_frame)
        except Exception as e:
            cancel()
            print("hata oluştu: ", e)
            return

    def cancel():
        global camera, camera_lock, fingerprint_thread_active
        fingerprint_thread_active = False
        with camera_lock:
            if camera is not None:
                camera.release()
                camera = None
        camera_window.destroy()
        root.destroy()  # Ana pencereyi kapat
        root.root.deiconify()
        root.root.lift()

    update_frame()
    cancel_button = tk.Button(
        button_frame,
        text="İptal",
        font=("Arial", 16),
        bg="#630e0e",
        fg="white",
        command=cancel
    )

    cancel_button.pack(expand=True, fill=tk.BOTH)  # Buton alt kısma yaslanır

    def on_close():
        with camera_lock:
            if camera is not None:
                camera.release()
        camera_window.destroy()

    camera_window.protocol("WM_DELETE_WINDOW", on_close)
