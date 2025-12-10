import tkinter as tk
from tkinter import messagebox
import time
import threading
import paks_database
import sound_config
import video_stream
import fingerprint_config as fpconfig
from Logger import LOGGER




def is_valid_TR_ID(value : str):
    #value = str(value)

    if not len(value) == 11:
        return False

    if not value.isdigit():
        return False

    if int(value[0]) == 0:
        return False

    digits = [int(d) for d in str(value)]

    if not sum(digits[:10]) % 10 == digits[10]:
        return False

    if not (((7 * sum(digits[:9][-1::-2])) - sum(digits[:9][-2::-2])) % 10) == digits[9]:
        return False

    return True

# Kimlik numarası giriş ekranını açacak fonksiyon
def open_tckn_screen(root): 
    video_stream.fingerprint_thread_active=True
    # Yeni pencereyi oluştur 
    tckn_window = tk.Toplevel()
    tckn_window.root = root
    tckn_window.attributes("-fullscreen", True)
    tckn_window.resizable(False, False)
    tckn_window.title("Kimlik Numarası Girişi")
    #tckn_window.geometry("800x480")
    tckn_window.geometry("1024x600")
    tckn_window.resizable(False, False)
    tckn_window.config(bg="#630e0e")
    tckn_window.lift()

    # Kimlik numarası için etiket
    tckn_label = tk.Label(tckn_window, text="TCKN Girişi:", font=("Arial", 16))
    tckn_label.pack(pady=10)

    # Kimlik numarası gösterilecek etiket
    tckn_entry = tk.Label(tckn_window, text="", font=("Arial", 20), width=40, height=2, relief="solid")
    #tckn_entry = tk.Label(tckn_window, text="", font=("Arial", 20), width=25, height=1, relief="solid")
    tckn_entry.pack(pady=10)  
    sound_config.play_sound(sound_config.soundTC)
   

    # Sayısal tuş takımı
    def append_number(number):
        current_text = tckn_entry.cget("text")
        if len(current_text) < 11:  # Maksimum 11 haneli TCKN
            tckn_entry.config(text=current_text + str(number))

    def backspace():
        current_text = tckn_entry.cget("text")
        tckn_entry.config(text=current_text[:-1])  # Son karakteri sil
        
    def create_modal_error_window(parent, message):
        # Modal pencere oluşturuyoruz
        error_window = tk.Toplevel(parent)
        error_window.title("Hata")
        
        error_window.transient(parent)  # Ana pencereye bağlı yapıyoruz
        # Pencerenin modal olmasını sağlıyoruz
        error_window.grab_set()  # Tüm tıklamaları bu pencereye yönlendir
        error_window.geometry("450x100")  # Pencere boyutu
        error_window.resizable(False, False)  # Boyutlandırma kapalı
        
        # Hata mesajı etiketini ekliyoruz
        label = tk.Label(error_window, text=message, pady=20)
        label.pack()

        # Tamam butonu ekliyoruz
        ok_button = tk.Button(error_window, text="Tamam", command=lambda: on_error_window_close(parent, error_window))
        ok_button.pack()

        # Pencereyi ekranda ortaya yerleştiriyoruz
        #error_window.eval('tk::PlaceWindow %s center' % error_window.winfo_toplevel())
        center_window(error_window)
        
        # Toplevel pencere kapatıldığında ana pencereyi geri getir
        error_window.protocol("WM_DELETE_WINDOW", lambda: on_error_window_close(parent, error_window))
        error_window.wait_window()
        
        
    def on_error_window_close(parent, error_window):
        # Hata penceresi kapandığında ana pencereyi geri getir ve bağlı pencereyi kapat
        parent.deiconify()  # Ana pencereyi görünür yap
        error_window.destroy()  # Hata penceresini kapat
        if isinstance(parent, tk.Toplevel):
            parent.destroy()  # Bağlı pencereyi kapat
            
        if 'root' in globals() and isinstance(root, tk.Tk):
            root.deiconify()
            root.lift()
        
    def center_window(window):
        # Pencereyi ekranın ortasında yerleştiriyoruz
        window.update_idletasks()  # Pencerenin boyutlarını güncelle
        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Pencereyi ekranın ortasına yerleştiriyoruz
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        window.geometry(f'{width}x{height}+{x}+{y}')

    def submit_tckn():
        root.withdraw()
        tckn = tckn_entry.cget("text")
        
        if not is_valid_TR_ID(tckn):
            sound_config.play_sound(sound_config.soundTCError)
            create_modal_error_window(tckn_window, "Geçersiz TCKN. Lütfen geçerli bir TC Kimlik Numarası girin.")
      
            #messagebox.showerror("Hata", "Geçersiz TCKN. Lütfen geçerli bir TC Kimlik Numarası girin.")
            tckn_window.destroy()
            root.deiconify()
            root.lift()
            return
            
        person_tckn_result=fpconfig.database.selectPeopleWithTCKN(tckn)
        if person_tckn_result is None or len(person_tckn_result) < 1:
            sound_config.play_sound(sound_config.soundTCUndefined)
            create_modal_error_window(tckn_window, "Sistemde Kayıtlı Olmayan TCKN Girildi.")
      
            #messagebox.showerror(title="Hata", message="Sistemde Kayıtlı Olmayan TCKN Girildi.")
            tckn_window.destroy()
            root.deiconify()
            root.lift()
            return
            
        person_id_info = person_tckn_result[0][0]        
        person_fingerprints = fpconfig.database.select_person_fingerprints(person_id_info)
        if len(person_fingerprints)<1:
            sound_config.play_sound(sound_config.soundUndefined)
            create_modal_error_window(tckn_window, "Sistemde Parmak İzi Kayıtlı Olmayan TCKN Girildi.")
            #messagebox.showerror(title="Hata", message="Sistemde Parmak İzi Kayıtlı Olmayan TCKN Girildi.")
            
            
            LOGGER.WriteLog("PlaySound Error (Find Finger empty db)")
            tckn_window.destroy()
            root.deiconify()
            root.lift()
            return
            
        
        video_stream_thread = threading.Thread(target=video_stream.open_camera, args=(tckn_window,))
        video_stream_thread.start()
        time.sleep(1)
        find_finger_thread = threading.Thread(target=fpconfig.find_finger, args=(person_fingerprints, person_id_info, tckn,))
        find_finger_thread.start() 
        




    # Sayısal tuş takımı ve Backspace, OK butonları
    keypad_frame = tk.Frame(tckn_window)
    keypad_frame.pack()

    # Sayılar
    buttons = [
        (1, 0, 0), (2, 0, 1), (3, 0, 2),
        (4, 1, 0), (5, 1, 1), (6, 1, 2),
        (7, 2, 0), (8, 2, 1), (9, 2, 2),
        ("←", 3, 0), (0, 3, 1), ("TAMAM", 3, 2)
    ]

    for (text, row, col) in buttons:
        button = tk.Button(keypad_frame, text=str(text), font=("Arial", 16), width=19, height=3)
        #button = tk.Button(keypad_frame, text=str(text), font=("Arial", 16), width=15, height=2)
        button.grid(row=row, column=col, padx=10, pady=5)

        if text == "←":
            button.config(command=backspace)
        elif text == "TAMAM":
            button.config(command=submit_tckn)
        else:
            button.config(command=lambda number=text: append_number(number))

    # Pencereyi aç
    tckn_window.mainloop()
