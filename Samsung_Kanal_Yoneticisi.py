"""
Samsung TV Otomatik Kanal Sıralama ve Düzenleme Yöneticisi (Görsel Arayüz)
------------------------------------------------------------------------
Kullanıcı Dostu Görsel Arayüz:
1. USB belleği (E:\ vb.) anlık takip eder.
2. TV'den gelen kanal listesini tek tıkla otomatik temizler ve sıralar:
   - Sadece Yüksek Kalite (Full HD) kanalları tutar, SD kopyaları eler.
   - Tüm dini kanalları ve dini radyoları tamamen siler.
   - Tüm şifreli, çöp, tanıtım ve boş yayınları siler.
   - Ülke TV, Ekol TV, Ekotürk'ü engeller.
   - 1-52: Ana Ulusal HD TV kanalları
   - 61-85: Popüler Müzik Radyoları (TV kumandasıyla ortak dinleme)
3. Oluşan listeyi canlı tabloda gösterir.
4. İstenirse ChanSort ile manuel düzenleme imkanı sunar.
"""

import os
import sys
import time
import shutil
import string
import ctypes
import threading
import subprocess
import sqlite3
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHANSORT_EXE = os.path.join(BASE_DIR, "ChanSort", "ChanSort_2026-09-28", "ChanSort.exe")
WORK_DIR = os.path.join(BASE_DIR, "processed_final")
OUTPUT_LOCAL_ZIP = os.path.join(BASE_DIR, "Channel_list_T-KTM2DEUC-1400.2_DUZENLENMIS.zip")

def get_removable_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drive_path = f"{letter}:\\"
            dtype = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
            if dtype == 2: # DRIVE_REMOVABLE
                drives.append(drive_path)
        bitmask >>= 1
    if not drives and os.path.exists("E:\\"):
        drives.append("E:\\")
    return drives

def find_channel_files():
    candidates = []
    search_dirs = get_removable_drives()
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    search_dirs.extend([BASE_DIR, desktop])
    
    seen = set()
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        try:
            for root, dirs, files in os.walk(sdir):
                rel = os.path.relpath(root, sdir)
                if rel.count(os.sep) >= 2:
                    continue
                for f in files:
                    lf = f.lower()
                    if (lf.startswith("channel_list_") and lf.endswith(".zip")) or lf.endswith(".scm"):
                        if "gta" in root.lower() or "duzenlenmis" in lf or "yedek" in lf:
                            continue
                        full_path = os.path.join(root, f)
                        if full_path not in seen:
                            seen.add(full_path)
                            candidates.append(full_path)
        except Exception:
            pass
    return candidates

def decode_name(val):
    if not val:
        return ""
    if isinstance(val, str):
        try:
            return val.encode('utf-16-be').decode('utf-16-le').strip('\x00')
        except Exception:
            return val
    return str(val)

def encode_name(text):
    return text.encode('utf-16-le').decode('utf-16-be')

class SamsungChannelApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Samsung TV Kanal Düzenleyici & Temizleyici (HD & Özel Liste)")
        self.geometry("960x720")
        self.minsize(880, 620)
        self.configure(bg="#0F172A")
        
        self.detected_file = None
        self.running = True
        
        self.setup_styles()
        self.build_ui()
        
        self.watcher_thread = threading.Thread(target=self.watch_drives, daemon=True)
        self.watcher_thread.start()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        
        style.configure("TNotebook", background="#0F172A", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 8], background="#1E293B", foreground="#94A3B8")
        style.map("TNotebook.Tab", background=[("selected", "#2563EB")], foreground=[("selected", "#FFFFFF")])
        
        style.configure("Card.TFrame", background="#1E293B", relief="flat")
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=24, background="#1E293B", foreground="#F8FAFC", fieldbackground="#1E293B")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#334155", foreground="#F8FAFC")
        style.map("Treeview", background=[("selected", "#2563EB")], foreground=[("selected", "#FFFFFF")])

    def build_ui(self):
        # Header Banner
        header = tk.Frame(self, bg="#1E3A8A", height=75)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        lbl_t = tk.Label(header, text="📺 Samsung TV Otomatik Kanal & Radyo Düzenleyici", font=("Segoe UI", 15, "bold"), bg="#1E3A8A", fg="#FFFFFF")
        lbl_t.pack(anchor="w", padx=20, pady=(10, 0))

        lbl_sub = tk.Label(header, text="Otomatik USB Algılama • %100 Full HD Yayınlar • Sıfır Dini Kanal • Özel Radyo Dizilimi", font=("Segoe UI", 9), bg="#1E3A8A", fg="#93C5FD")
        lbl_sub.pack(anchor="w", padx=20, pady=(2, 0))

        # Ana Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tab_main = tk.Frame(self.notebook, bg="#0F172A", padx=10, pady=10)
        self.notebook.add(tab_main, text="  ⚡ Hızlı İşlemler & Durum  ")

        tab_table = tk.Frame(self.notebook, bg="#0F172A", padx=10, pady=10)
        self.notebook.add(tab_table, text="  📋 Aktif Kanal Sıralaması  ")

        tab_guide = tk.Frame(self.notebook, bg="#0F172A", padx=10, pady=10)
        self.notebook.add(tab_guide, text="  📖 TV Kullanım Rehberi  ")

        self.build_tab_main(tab_main)
        self.build_tab_table(tab_table)
        self.build_tab_guide(tab_guide)

    def build_tab_main(self, parent):
        # Durum Kartı
        card_status = tk.Frame(parent, bg="#1E293B", padx=15, pady=15, highlightthickness=1, highlightbackground="#334155")
        card_status.pack(fill=tk.X, pady=(0, 15))

        tk.Label(card_status, text="Cihaz & Dosya Algılama", font=("Segoe UI", 11, "bold"), bg="#1E293B", fg="#F8FAFC").pack(anchor="w")

        self.lbl_usb = tk.Label(card_status, text="• USB Bellek: Taranıyor...", font=("Segoe UI", 10), bg="#1E293B", fg="#CBD5E1")
        self.lbl_usb.pack(anchor="w", pady=(6, 2))

        self.lbl_file = tk.Label(card_status, text="• Kanal Dosyası: Aranıyor...", font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#F59E0B")
        self.lbl_file.pack(anchor="w", pady=2)

        self.lbl_file_path = tk.Label(card_status, text="", font=("Segoe UI", 8), bg="#1E293B", fg="#64748B")
        self.lbl_file_path.pack(anchor="w", pady=2)

        # Büyük Butonlar Alanı
        card_actions = tk.Frame(parent, bg="#1E293B", padx=15, pady=15, highlightthickness=1, highlightbackground="#334155")
        card_actions.pack(fill=tk.X, pady=(0, 15))

        tk.Label(card_actions, text="Kanal Listesini Düzenleme Seçenekleri", font=("Segoe UI", 11, "bold"), bg="#1E293B", fg="#F8FAFC").pack(anchor="w", pady=(0, 10))

        btn_row = tk.Frame(card_actions, bg="#1E293B")
        btn_row.pack(fill=tk.X, pady=5)

        # 1. Ana Otomatik Buton
        self.btn_auto = tk.Button(
            btn_row, 
            text="⚡ TEK TIKLA OTOMATİK TEMİZLE VE SIRALA", 
            font=("Segoe UI", 11, "bold"), 
            bg="#16A34A", 
            fg="#FFFFFF", 
            activebackground="#15803D", 
            activeforeground="#FFFFFF",
            relief="flat", 
            padx=16, 
            pady=10, 
            cursor="hand2",
            command=self.run_auto_clean_thread
        )
        self.btn_auto.pack(side=tk.LEFT, padx=(0, 10))

        # 2. ChanSort Butonu
        self.btn_chansort = tk.Button(
            btn_row, 
            text="🛠️ ChanSort ile Manuel Aç", 
            font=("Segoe UI", 10), 
            bg="#3B82F6", 
            fg="#FFFFFF", 
            activebackground="#2563EB", 
            activeforeground="#FFFFFF",
            relief="flat", 
            padx=12, 
            pady=10, 
            cursor="hand2",
            command=self.open_chansort
        )
        self.btn_chansort.pack(side=tk.LEFT, padx=(0, 10))

        # 3. Manuel Seçim
        btn_browse = tk.Button(
            btn_row, 
            text="📂 Manuel Dosya Seç", 
            font=("Segoe UI", 10), 
            bg="#475569", 
            fg="#FFFFFF", 
            relief="flat", 
            padx=12, 
            pady=10, 
            cursor="hand2",
            command=self.browse_manual
        )
        btn_browse.pack(side=tk.LEFT)

        # Bilgi Notu Kutusu
        card_info = tk.Frame(parent, bg="#1E293B", padx=15, pady=15, highlightthickness=1, highlightbackground="#334155")
        card_info.pack(fill=tk.BOTH, expand=True)

        tk.Label(card_info, text="Otomatik Sıralamanın Uygulayacağı Kurallar:", font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#38BDF8").pack(anchor="w", pady=(0, 6))

        rules = (
            "✔ 1 - 9 Arası: Ana Ulusal HD Kanallar (TRT 1, ATV, KANAL D, SHOW, STAR, NOW, TV8, KANAL 7, BEYAZ)\n"
            "✔ 10 - 15 Arası: Belgesel & Dizi HD (DMAX, TLC, TRT Belgesel, Teve2, CNBC-e, TGRT Belgesel)\n"
            "✔ 16 - 18 Arası: TV Müzik (TRT Müzik, Dream Türk, NR1 Türk)\n"
            "✔ 19 - 28 Arası: Seçkin Haber HD (NTV, TRT Haber, CNN Türk, Haber Global, Sözcü, Habertürk, Halk TV...)\n"
            "✔ 29 - 36 Arası: Spor HD (beIN Sports Haber, TRT Spor, A Spor, HT Spor, TV8.5, TJK TV)\n"
            "✔ 61 - 85 Arası: Popüler Müzik Radyoları (Kral Pop, Kral FM, Power FM, PowerTürk, Metro, Süper, Slow Türk...)\n"
            "❌ Dini TV ve Dini Radyolar: Sıfırlandı (Tamamı silindi)\n"
            "❌ Şifreli & Çöp Kanallar: Boş sinyaller ve şifreli yayınlar tamamen kaldırıldı\n"
            "❌ İstenmeyen Kanallar: Ülke TV, Ekol TV, Ekotürk engellendi"
        )
        tk.Label(card_info, text=rules, font=("Segoe UI", 9), bg="#1E293B", fg="#CBD5E1", justify=tk.LEFT).pack(anchor="w")

        self.lbl_progress = tk.Label(card_info, text="", font=("Segoe UI", 10, "bold"), bg="#1E293B", fg="#22C55E")
        self.lbl_progress.pack(anchor="w", pady=(10, 0))

    def build_tab_table(self, parent):
        tk.Label(parent, text="Mevcut Düzenlenmiş Kanal ve Radyo Listesi", font=("Segoe UI", 11, "bold"), bg="#0F172A", fg="#F8FAFC").pack(anchor="w", pady=(0, 8))

        cols = ("No", "Tür", "Kanal Adı", "Kalite")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        self.tree.heading("No", text="No")
        self.tree.heading("Tür", text="Tür")
        self.tree.heading("Kanal Adı", text="Kanal / İstasyon Adı")
        self.tree.heading("Kalite", text="Yayın Kalitesi")

        self.tree.column("No", width=70, anchor="center")
        self.tree.column("Tür", width=80, anchor="center")
        self.tree.column("Kanal Adı", width=380, anchor="w")
        self.tree.column("Kalite", width=120, anchor="center")

        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.populate_treeview()

    def build_tab_guide(self, parent):
        canvas = tk.Canvas(parent, bg="#0F172A", highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#0F172A")

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        steps = [
            ("1. ADIM", "USB Belleği TV'ye Takın ve Kanal Listesini Alın", 
             "• USB belleği TV'nize takın.\n• Kumandadan Ayarlar (Settings) -> Yayın (Broadcasting) -> Uzman Ayarları -> Kanal Listesini Aktarın bölümüne gelin.\n• 'USB'ye Ver' (Export) seçeneğine basın.\n• PIN kodu sorarsa 0000 girin."),
            ("2. ADIM", "USB Belleği Bilgisayara Takın", 
             "• USB belleği bilgisayarınıza takın.\n• Bu program açık olduğunda dosyayı anında yeşil renkle algılayacaktır.\n• '⚡ TEK TIKLA OTOMATİK TEMİZLE VE SIRALA' butonuna basın.\n• Program 2 saniye içinde listenizi filtreler, HD kanalları dizer ve USB'ye geri yazar."),
            ("3. ADIM", "USB Belleği TV'ye Geri Takın ve Yükleyin", 
             "• USB belleği çıkarıp tekrar TV'ye takın.\n• Aynı menüden (Yayın -> Uzman Ayarları -> Kanal Listesini Aktarın) bu kez 'USB'den Al' (Import) deyin.\n• Televizyonunuz kanalları anında yükleyip yeniden başlayacaktır. Tüm liste sıralı olarak kullanıma hazırdır!")
        ]

        for num, title, desc in steps:
            card = tk.Frame(scroll_frame, bg="#1E293B", padx=15, pady=12, highlightthickness=1, highlightbackground="#334155")
            card.pack(fill=tk.X, expand=True, pady=6, padx=5)
            tk.Label(card, text=num, font=("Segoe UI", 9, "bold"), bg="#2563EB", fg="#FFFFFF", padx=6, pady=2).pack(anchor="w")
            tk.Label(card, text=title, font=("Segoe UI", 11, "bold"), bg="#1E293B", fg="#38BDF8").pack(anchor="w", pady=(4, 2))
            tk.Label(card, text=desc, font=("Segoe UI", 9), bg="#1E293B", fg="#CBD5E1", justify=tk.LEFT).pack(anchor="w")

    def watch_drives(self):
        last_found = None
        while self.running:
            removables = get_removable_drives()
            files = find_channel_files()

            usb_text = f"• USB Bellek: {', '.join(removables)} Algılandı" if removables else "• USB Bellek: Takılı Değil"
            
            if files:
                current_file = files[0]
                file_text = f"• Kanal Dosyası: BULUNDU ({os.path.basename(current_file)})"
                detail_text = f"Konum: {current_file}"
                color = "#22C55E"
                self.detected_file = current_file
            else:
                self.detected_file = None
                file_text = "• Kanal Dosyası: USB'de Aranıyor..."
                detail_text = "TV'den 'USB'ye Ver' yapılmış bir .zip veya .scm dosyası bekleniyor."
                color = "#F59E0B"

            self.after(0, self.update_status, usb_text, file_text, detail_text, color)
            time.sleep(2)

    def update_status(self, usb_text, file_text, detail_text, color):
        self.lbl_usb.config(text=usb_text)
        self.lbl_file.config(text=file_text, fg=color)
        self.lbl_file_path.config(text=detail_text)

    def run_auto_clean_thread(self):
        self.btn_auto.config(state=tk.DISABLED)
        self.lbl_progress.config(text="İşleniyor, lütfen bekleyin...")
        threading.Thread(target=self.do_auto_clean, daemon=True).start()

    def do_auto_clean(self):
        script_path = os.path.join(BASE_DIR, "finalize_clean_hd_channels.py")
        if os.path.exists(script_path):
            res = subprocess.run([sys.executable, script_path], capture_output=True, text=True, encoding="utf-8")
            if res.returncode == 0:
                self.after(0, self.on_clean_success)
            else:
                self.after(0, lambda: messagebox.showerror("Hata", f"İşlem sırasında hata oluştu:\n{res.stderr}"))
        else:
            self.after(0, lambda: messagebox.showerror("Hata", f"finalize_clean_hd_channels.py bulunamadı."))
        self.after(0, lambda: self.btn_auto.config(state=tk.NORMAL))

    def on_clean_success(self):
        self.lbl_progress.config(text="✔ İşlem Tamamlandı! USB güncellendi.")
        messagebox.showinfo(
            "Başarılı!", 
            "Kanal listeniz tüm isteklerinize göre düzenlendi:\n\n"
            "• Sadece Full HD yayınlar bırakıldı.\n"
            "• Dini kanallar ve radyolar tamamen silindi.\n"
            "• Şifreli/çöp yayınlar temizlendi.\n"
            "• Radyolar 61'den itibaren dizildi.\n"
            "• Dosya doğrudan USB belleğinize kaydedildi!\n\n"
            "Şimdi USB'yi TV'ye takıp [USB'den Al] diyebilirsiniz."
        )
        self.populate_treeview()

    def populate_treeview(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        zip_to_read = None
        for cand in [OUTPUT_LOCAL_ZIP, r"E:\Channel_list_T-KTM2DEUC-1400.2.zip"]:
            if os.path.exists(cand):
                zip_to_read = cand
                break
                
        if not zip_to_read:
            return
            
        try:
            with zipfile.ZipFile(zip_to_read, 'r') as z:
                z.extract("dvbs", path=WORK_DIR)
                
            db_path = os.path.join(WORK_DIR, "dvbs")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT major, srvName, srvType, resInfoHeight FROM SRV WHERE major > 0 ORDER BY major")
            rows = cur.fetchall()
            conn.close()
            
            for major, raw_name, srvType, h in rows:
                name = decode_name(raw_name)
                t = "Radyo" if srvType == 2 else "TV"
                q = "Full HD" if (srvType == 25 or "HD" in name.upper() or h >= 720) else ("-" if srvType == 2 else "SD")
                self.tree.insert("", tk.END, values=(major, t, name, q))
        except Exception as e:
            pass

    def open_chansort(self):
        if not os.path.exists(CHANSORT_EXE):
            messagebox.showerror("Hata", "ChanSort.exe bulunamadı.")
            return
        target = self.detected_file or r"E:\Channel_list_T-KTM2DEUC-1400.2.zip"
        if os.path.exists(target):
            subprocess.Popen([CHANSORT_EXE, target])
        else:
            subprocess.Popen([CHANSORT_EXE])

    def browse_manual(self):
        f = filedialog.askopenfilename(
            title="Kanal Dosyası Seçin",
            filetypes=[("Samsung Dosyaları (*.zip, *.scm)", "*.zip;*.scm"), ("Tüm Dosyalar", "*.*")]
        )
        if f:
            self.detected_file = f
            self.lbl_file.config(text=f"• Dosya: {os.path.basename(f)}", fg="#22C55E")
            self.lbl_file_path.config(text=f)

if __name__ == "__main__":
    app = SamsungChannelApp()
    app.mainloop()
