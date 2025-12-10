import tkinter as tk

from PIL import Image, ImageTk  # Resim boyutlandırmak için gerekli

from tckn_screen import open_tckn_screen  # Kimlik numarası giriş ekranını başka bir dosyadan çağır

import RoutineJobs

from datetime import datetime

import sys

routine_jobs=RoutineJobs.RoutineJobs()




 # ilk çağrı

# Ana pencereyi oluştur
root = tk.Tk()
root.title("RSA PAKS")
root.attributes("-fullscreen", True)
root.resizable(False, False)
#root.geometry("800x480")  # Raspberry Pi ekranı için uygun bir boyut

window_width=root.winfo_width()
window_height=root.winfo_height()

# Solda bir resim eklemek için bir çerçeve
left_frame = tk.Frame(root, width=768, height=600)
#left_frame = tk.Frame(root, width=600, height=480)
left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)  # Boşlukları kaldır
left_frame.pack_propagate(False)




# Resmi yükle ve boyutlandır
try:
    # Resmi PIL ile yükleyip boyutlandırıyoruz
    img = Image.open("PAKS-PHOTO/paks.png")  # Resim dosyasının yolu
    img = img.resize((768, 600), Image.Resampling.LANCZOS)  # Resmi boyutlandır
    #img = img.resize((600, 480), Image.Resampling.LANCZOS)  # Resmi boyutlandır
    photo = ImageTk.PhotoImage(img)

    # Resmi etiket içine ekliyoruz
    #image_label = tk.Label(left_frame, image=photo)
    #image_label.image = photo  # Referans sakla
    #image_label.pack(expand=True, fill=tk.BOTH)
    
    # Canvas ile resim ve saat gösterimi
    canvas = tk.Canvas(left_frame, width=768, height=600, highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    
    time_text = canvas.create_text(
    760, 590,
    text="Yükleniyor...",
    fill="#630e0e",  # Buraya özel rengin geldi
    font=("Helvetica", 25, "bold"),
    anchor=tk.SE)    
except Exception as e:
    print(f"Resim yüklenemedi: {e}")

# Sağda bir buton eklemek için bir çerçeve
right_frame = tk.Frame(root, width=256, height=600, bg="lightgray")
#right_frame = tk.Frame(root, width=200, height=480, bg="lightgray")
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=0, pady=0)  # Boşlukları kaldır
right_frame.pack_propagate(False)

# "TCKN Giriş" butonu, sağ çerçevenin tamamını kaplasın
tckn_button = tk.Button(
    right_frame,
    text="TCKN Giriş",
    font=("Arial", 16),
    bg="#630e0e",
    fg="white",
    command=lambda: open_tckn_screen(root)
)
tckn_button.pack(expand=True, fill=tk.BOTH)  # Çerçevenin tamamını kapla

def update_time():
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    canvas.itemconfig(time_text, text=now)
    canvas.after(1000, update_time)

update_time() 



# Pencereyi çalıştır
try:
    root.mainloop()
except KeyboardInterrupt:
    print("Kullanıcı Ctrl+C yaptı, çıkılıyor...")
    sys.exit(-1)
