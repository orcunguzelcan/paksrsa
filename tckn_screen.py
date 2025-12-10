import tkinter as tk
import threading
import time
import video_stream
import fingerprint_config as fpconfig
import sound_config
from Logger import LOGGER


def start_scan_process(root_main):
    """
    Kamera ve Tarama Ekranı.
    Timeout (Zaman Aşımı) desteği eklendi.
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
    scan_window.attributes("-fullscreen", True)
    scan_window.state('normal')
    scan_window.lift()
    scan_window.focus_force()
    scan_window.grab_set()

    info_label = tk.Label(
        scan_window,
        text="Parmak İzi Okutmak İçin Dokunun",
        font=("Arial", 40, "bold"),
        fg="white",
        bg="#630e0e",
        pady=20
    )
    info_label.pack(side=tk.BOTTOM, fill=tk.X)

    video_label = tk.Label(scan_window, bg="black")
    video_label.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

    scan_window.update_idletasks()
    scan_window.update()
    root_main.withdraw()

    # --- KAPATMA FONKSİYONU ---
    def on_close(event=None):
        """Pencereyi kapatır ve ana ekrana döner."""
        LOGGER.WriteLog("Tarama ekranı kapatılıyor (Timeout veya Manuel).")

        # Tarama bittiği için kilidi kaldırıyoruz
        video_stream.fingerprint_thread_active = False

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

    # --- TIMEOUT DİNLEYİCİSİ (YENİ) ---
    video_label.bind("<<Timeout>>", on_close)
    # ----------------------------------

    time.sleep(0.5)
    fp_thread = threading.Thread(target=fpconfig.find_finger_1_to_N, args=(scan_window, root_main))
    fp_thread.start()

    scan_window.protocol("WM_DELETE_WINDOW", on_close)
    scan_window.mainloop()