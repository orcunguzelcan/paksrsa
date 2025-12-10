import tkinter as tk
from PIL import Image, ImageTk  # Resim boyutlandırmak için gerekli

# Ana pencereyi oluştur
root = tk.Tk()
root.title("Dokunmatik Arayüz")
root.geometry("800x480")  # Raspberry Pi ekranı için uygun bir boyut

# Solda bir resim eklemek için bir çerçeve
left_frame = tk.Frame(root, width=600, height=480)
left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)  # Boşlukları kaldır
left_frame.pack_propagate(False)

# Resmi yükle ve boyutlandır
try:
    # Resmi PIL ile yükleyip boyutlandırıyoruz
    img = Image.open("PAKS-PHOTO/paks.png")  # Resim dosyasının yolu
    img = img.resize((600, 480), Image.Resampling.LANCZOS)  # Resmi boyutlandır
    photo = ImageTk.PhotoImage(img)

    # Resmi etiket içine ekliyoruz
    image_label = tk.Label(left_frame, image=photo)
    image_label.image = photo  # Referans sakla
    image_label.pack(expand=True, fill=tk.BOTH)
except Exception as e:
    print(f"Resim yüklenemedi: {e}")

# Sağda bir buton eklemek için bir çerçeve
right_frame = tk.Frame(root, width=200, height=480, bg="lightgray")
right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=0, pady=0)  # Boşlukları kaldır
right_frame.pack_propagate(False)

# "TCKN Giriş" butonu, sağ çerçevenin tamamını kaplasın
tckn_button = tk.Button(
    right_frame,
    text="TCKN Giriş",
    font=("Arial", 16),
    bg="#630e0e",
    fg="white"
)
tckn_button.pack(expand=True, fill=tk.BOTH)  # Çerçevenin tamamını kapla

# Pencereyi çalıştır
root.mainloop()
