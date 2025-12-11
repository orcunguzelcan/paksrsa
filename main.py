import tkinter as tk
from PIL import Image, ImageTk
import tckn_screen  # Tarama ekranı modülü
import RoutineJobs
from datetime import datetime
import sys
import video_stream
import threading
import user_process
import paks_database

try:
    paks_database.initialize_database_if_needed()
except Exception as e:
    print("Veritabanı ilk kurulumda hata:", e)

try:
    video_stream.reset_camera_device()
except Exception as e:
    # Reset başarısız olsa bile uygulama devam etsin
    print("Kamera reset denemesinde hata:", e)

# --- 1. KAMERA SERVİSİNİ BAŞLAT ---
video_stream.start_camera_service()

server_thread = threading.Thread(target=user_process.run, daemon=True)
server_thread.start()
# --- 2. ARKA PLAN İŞLERİNİ BAŞLAT ---
routine_jobs = RoutineJobs.RoutineJobs()

# --- 3. ANA PENCEREYİ OLUŞTUR ---
root = tk.Tk()
root.title("RSA PAKS")
root.attributes("-fullscreen", True)
root.resizable(False, False)

# Ekran boyutlarını al
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# --- 4. ARKA PLAN VE SAAT ---
canvas = tk.Canvas(root, width=screen_width, height=screen_height, highlightthickness=0)
canvas.pack(fill=tk.BOTH, expand=True)

background_photo = None
time_text = None

try:
    # Resmi yükle ve EKRAN BOYUTUNA GÖRE tam kapla
    img = Image.open("PAKS-PHOTO/paks.png")
    img = img.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
    background_photo = ImageTk.PhotoImage(img)

    # Resmi canvas'a yerleştir
    canvas.create_image(0, 0, anchor=tk.NW, image=background_photo)

    # --- SAAT AYARI (DEĞİŞTİ) ---
    # Konum: Ekranın tam ortası (width/2) ve butonun altı (height * 0.85)
    # Boyut: 40 Punto
    time_text = canvas.create_text(
        screen_width / 2,  # Yatayda Tam Orta
        screen_height * 0.90,  # Dikeyde %85 aşağısı (Butonun altı)
        text=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        fill="#630e0e",
        font=("Helvetica", 50, "bold"),  # Font BÜYÜTÜLDÜ
        anchor=tk.CENTER  # Metni merkezden hizala
    )
except Exception as e:
    print(f"Resim yüklenemedi: {e}")
    canvas.config(bg="white")

# --- 5. ORTA BUTON ---
scan_button = tk.Button(
    root,
    text="PARMAK İZİNİZİ OKUTMAK İÇİN BUTONA BASINIZ",
    font=("Arial", 28, "bold"),
    bg="#630e0e",
    fg="white",
    activebackground="red",
    activeforeground="white",
    bd=5,
    relief="raised",
    cursor="hand2",
    command=lambda: tckn_screen.start_scan_process(root)
)

# Butonun Konumu (Ekranın %65 aşağısında)
scan_button.place(relx=0.5, rely=0.60, anchor=tk.CENTER, width=1000, height=200)


# --- 6. SAAT GÜNCELLEME ---
def update_time():
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    try:
        if canvas is not None and time_text is not None:
            canvas.itemconfig(time_text, text=now)
    except Exception:
        pass
    root.after(1000, update_time)


update_time()


def on_root_close():
    # Önce UI güncellemeyi durdur
    video_stream.stop_ui_update()
    # Sonra kamera servisini kapat
    video_stream.stop_camera_service()
    # En son tkinter penceresini kapat
    root.destroy()
    sys.exit(0)

root.protocol("WM_DELETE_WINDOW", on_root_close)

# --- 7. BAŞLAT ---
try:
    root.mainloop()
except KeyboardInterrupt:
    print("Çıkış yapılıyor...")
    video_stream.stop_ui_update()
    video_stream.stop_camera_service()
    sys.exit(-1)