import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import json
import sys
import shutil
import requests
import uuid
import webbrowser
import time
from pathlib import Path
import psutil
import socket
import platform

IS_WINDOWS = sys.platform == "win32"

try:
    import winreg
except ImportError:
    winreg = None

# --- KONFIGURASI ---
API_URL = "https://script.google.com/macros/s/AKfycby3N_n9IgqkwkE9FANxylBwW6_lCEOBNeWz7FWEVPEfkbFzcnrpk1VzJwY5L_beQhh6RA/exec"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# === BUAT OTOMATIS FOLDER SESI BERSAMA SAAT APLIKASI DIBUKA ===
SHARED_SESSION_DIR = BASE_DIR / "browser-data"
SHARED_SESSION_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = BASE_DIR / "config.json"
STATUS_LOGIN_FILE = BASE_DIR / "login_status.json"
LICENSE_FILE = BASE_DIR / ".lic"
STAT_FILE = BASE_DIR / "data" / "total_stats.json" 

# === BUAT OTOMATIS FOLDER UPLOADER 1 - 8 SAAT APLIKASI DIBUKA ===
for i in range(1, 9):
    p_folder = BASE_DIR / f"browser-data-u{i}"
    p_folder.mkdir(parents=True, exist_ok=True)

try:
    sumber_login = BASE_DIR / "browser-data-u1"
    if sumber_login.exists() and any(sumber_login.iterdir()):
        for i in range(5, 9):
            target_folder = BASE_DIR / f"browser-data-u{i}"
            if not any(target_folder.iterdir()):
                shutil.copytree(sumber_login, target_folder, dirs_exist_ok=True)
except Exception:
    pass

processes = []
try:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        config["status"] = "STOPPED"
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
except Exception:
    pass

spinner_idx = 0
spinner_chars = ["|", "/", "-", "\\"]  
GLOBAL_IS_UPLOADING = False 
last_batch_state = [] 

# --- TEMA WARNA (DARK MODE REACT) ---
BG_MAIN = "#0f1115"
BG_PANEL = "#12151a"
BG_INPUT = "#181c24"
BORDER = "#1e2330"
TEXT_MAIN = "#e0e2e5"
TEXT_MUTED = "#64748b"
CYAN = "#06b6d4"
RED = "#e11d48"
GREEN = "#10b981"
ORANGE = "#f59e0b"

def get_max_allowed_workers():
    try:
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        if ram_gb <= 8:
            return 4  
        else:
            return 8  
    except:
        return 4

def get_device_id():
    try:
        if winreg and IS_WINDOWS:
            registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(machine_guid)
        else:
            return str(uuid.getnode())
    except Exception:
        return str(uuid.getnode())

def verify_with_server(code):
    try:
        params = {"kode": code, "id": get_device_id()}
        r = requests.get(API_URL, params=params, timeout=10)
        data = r.json()
        return data.get("status") in ["SUCCESS", "ACTIVE"]
    except:
        return True

def check_activation():
    if LICENSE_FILE.exists():
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            saved_code = f.read().strip()
        if verify_with_server(saved_code):
            return True
        else:
            LICENSE_FILE.unlink()
            messagebox.showwarning("Perangkat Berbeda", "Terdeteksi perubahan perangkat. Silakan konfirmasi ulang lisensi Anda.")

    while True:
        win = tk.Toplevel()
        win.title("Aktivasi Lisensi")
        win.geometry("450x300")
        win.configure(bg=BG_PANEL)
        win.resizable(False, False)
        win.grab_set()
        win.attributes("-topmost", True)

        result = {"ok": False}

        tk.Label(win, text="Masukkan Kode Lisensi", font=("Segoe UI", 10, "bold"), bg=BG_PANEL, fg=TEXT_MAIN).pack(pady=(20,5))
        entry_code = tk.Entry(win, width=40, font=("Segoe UI",11), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        entry_code.pack(pady=5, ipady=3)

        tk.Label(win, text="Masukkan Email (Untuk Keamanan)", font=("Segoe UI", 10, "bold"), bg=BG_PANEL, fg=TEXT_MAIN).pack(pady=(15,5))
        entry_email = tk.Entry(win, width=40, font=("Segoe UI",11), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        entry_email.pack(pady=5, ipady=3)

        def aktivasi():
            code = entry_code.get().strip()
            email = entry_email.get().strip()
            
            if not code or not email:
                messagebox.showwarning("Peringatan", "Kode lisensi dan Email wajib diisi!")
                return
                
            try:
                params = {"kode": code, "id": get_device_id(), "email": email}
                r = requests.get(API_URL, params=params, timeout=10)
                data = r.json()
                
                status_response = data.get("status")
                
                if status_response in ["SUCCESS", "ACTIVE"]:
                    with open(LICENSE_FILE, "w", encoding="utf-8") as f: 
                        f.write(code)
                    messagebox.showinfo("Berhasil", "Aktivasi / Pemindahan Lisensi Berhasil!")
                    result["ok"] = True
                    win.destroy()
                elif status_response == "INVALID_EMAIL":
                    messagebox.showerror("Error", "Email tidak cocok! Lisensi ini milik email lain.")
                elif status_response == "LOCKED":
                    messagebox.showerror("Error", "Kode sedang dipakai perangkat lain.\nMasukkan email yang benar untuk memindahkannya!")
                elif status_response == "REQUIRE_ACTIVATION":
                    messagebox.showerror("Error", "Data kosong, harap isi kode & email dengan benar.")
                else:
                    messagebox.showerror("Error", "Kode lisensi tidak valid!")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal koneksi:\n{e}")

        tk.Button(win, text="AKTIVASI", bg=CYAN, fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", width=25, command=aktivasi).pack(pady=20)
        
        win.wait_window()

        if result["ok"]: 
            return True
        else:
            if not messagebox.askyesno("Aktivasi", "Coba masukkan data lagi?"): 
                sys.exit()

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: pass
    return {
        "status": "IDLE", "watch_folder": "", "price": "", "price_video": "", 
        "fototree": "", "worker_count": 4, "mode": "kompres", 
        "convert_video": False, "rotation_dir": "clockwise"
    }

def save_config(new_config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=4)

def update_status():
    session_items_exist = any((BASE_DIR / f"browser-data-u{i}").exists() and any((BASE_DIR / f"browser-data-u{i}").iterdir()) for i in range(1, 9))
    if STATUS_LOGIN_FILE.exists() or session_items_exist:
        lbl_login.config(text="✓ Session Account: Terhubung", fg=GREEN)
    else:
        lbl_login.config(text="⚠ Session Account: Belum Login", fg=RED)

def check_login_status_loop():
    update_status()
    root.after(2000, check_login_status_loop)

def select_folder():
    folder = filedialog.askdirectory()
    if folder:
        entry_folder.delete(0, tk.END)
        entry_folder.insert(0, folder)

def logout():
    session_items = [f"browser-data-u{i}" for i in range(1, 9)] + ["browser-data", "login_status.json"]
    for item in session_items:
        path = BASE_DIR / item
        if path.exists():
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink()
    update_status()
    messagebox.showinfo("Logout", "Sesi berhasil dihapus.")

def run_login():
    EXE_EXT = ".exe" if IS_WINDOWS else ""
    login_script = f"login{EXE_EXT}"
    if getattr(sys, "frozen", False): 
        p_login = subprocess.Popen([str(BASE_DIR / login_script)])
    else: 
        p_login = subprocess.Popen([sys.executable, str(BASE_DIR / "login.py")])
    
    def cek_dan_duplikasi_sesi():
        if p_login.poll() is not None:
            sumber_folder = BASE_DIR / "browser-data"
            if sumber_folder.exists() and any(sumber_folder.iterdir()):
                for i in range(1, 9):
                    target_folder = BASE_DIR / f"browser-data-u{i}"
                    try:
                        if target_folder.exists():
                            shutil.rmtree(target_folder, ignore_errors=True)
                        shutil.copytree(sumber_folder, target_folder, dirs_exist_ok=True)
                    except Exception:
                        pass
                print("Sesi login utama berhasil disalin otomatis ke uploader 1-8!")
                update_status()
            return
        
        root.after(2000, cek_dan_duplikasi_sesi)

    root.after(2000, cek_dan_duplikasi_sesi)

def hitung_file_folder_sumber(folder_path):
    if not folder_path or not Path(folder_path).exists():
        return 0, 0
    
    foto_deteksi = 0
    video_deteksi = 0
    try:
        p = Path(folder_path)
        for f in p.rglob("*"):
            if f.is_file():
                if 'foto_asli' in f.parts:
                    continue
                ext = f.suffix.lower()
                if ext in ('.jpg', '.jpeg', '.png'):
                    foto_deteksi += 1
                elif ext in ('.mp4', '.mov'):
                    video_deteksi += 1
    except Exception as e:
        print(f"Error hitung file: {e}")
    return foto_deteksi, video_deteksi

def cek_status_belum_selesai():
    alasan = []
    if GLOBAL_IS_UPLOADING:
        alasan.append("• Proses upload browser sedang aktif berjalan.")
    processing_path = BASE_DIR / "data" / "processing"
    queue_path = BASE_DIR / "data" / "queue"
    processing_files = list(processing_path.glob("*.*")) if processing_path.exists() else []
    queue_files = list(queue_path.rglob("*.*")) if queue_path.exists() else []
    total_sisa = len(processing_files) + len([f for f in queue_files if f.is_file()])
    if total_sisa > 0:
        alasan.append(f"• Masih ada {total_sisa} file dalam folder antrean / proses.")
    f_berhasil, v_berhasil = 0, 0
    f_deteksi, v_deteksi = 0, 0
    if STAT_FILE.exists():
        try:
            with open(STAT_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
                f_berhasil = stats.get("total_foto", 0)
                v_berhasil = stats.get("total_video", 0)
                f_deteksi = stats.get("total_foto_deteksi", 0)
                v_deteksi = stats.get("total_video_deteksi", 0)
        except: pass
    if f_deteksi == 0 and v_deteksi == 0:
        f_deteksi, v_deteksi = hitung_file_folder_sumber(entry_folder.get().strip())
    total_berhasil = f_berhasil + v_berhasil
    total_deteksi = f_deteksi + v_deteksi
    if total_deteksi > 0 and total_berhasil < total_deteksi:
        kurang = total_deteksi - total_berhasil
        alasan.append(f"• Jumlah file terunggah ({total_berhasil}) belum match dengan total terdeteksi ({total_deteksi}). Kurang {kurang} file lagi.")
    return alasan

def start_all():
    session_exists = any((BASE_DIR / f"browser-data-u{i}").exists() and any((BASE_DIR / f"browser-data-u{i}").iterdir()) for i in range(1, 9))
    if not STATUS_LOGIN_FILE.exists() and not session_exists:
        messagebox.showwarning("Login", "Harap login ke Fotoyu terlebih dahulu!")
        return 
    
    folder_sumber = entry_folder.get().strip()
    if not folder_sumber:
        messagebox.showwarning("Folder", "Harap pilih folder sumber foto!")
        return

    f_deteksi_awal, v_deteksi_awal = hitung_file_folder_sumber(folder_sumber)

    try:
        STAT_FILE.parent.mkdir(exist_ok=True)
        now = time.time()
        
        if STAT_FILE.exists():
            try:
                with open(STAT_FILE, "r", encoding="utf-8") as f:
                    old_stats = json.load(f)
                    
                durasi_sebelumnya = old_stats.get("waktu_terakhir", now) - old_stats.get("waktu_mulai", now)
                if durasi_sebelumnya < 0: durasi_sebelumnya = 0
                
                init_data = {
                    "total_foto": old_stats.get("total_foto", 0), 
                    "total_video": old_stats.get("total_video", 0), 
                    "total_foto_deteksi": f_deteksi_awal,
                    "total_video_deteksi": v_deteksi_awal,
                    "waktu_mulai": now - durasi_sebelumnya,
                    "waktu_terakhir": now
                }
            except Exception:
                init_data = {"total_foto": 0, "total_video": 0, "total_foto_deteksi": f_deteksi_awal, "total_video_deteksi": v_deteksi_awal, "waktu_mulai": now, "waktu_terakhir": now}
        else:
            init_data = {"total_foto": 0, "total_video": 0, "total_foto_deteksi": f_deteksi_awal, "total_video_deteksi": v_deteksi_awal, "waktu_mulai": now, "waktu_terakhir": now}
            
        with open(STAT_FILE, "w", encoding="utf-8") as f:
            json.dump(init_data, f)
    except: pass
    
    max_limit = get_max_allowed_workers()
    try:
        worker_count = int(var_worker.get())
        if worker_count < 1: worker_count = 1
        if worker_count > max_limit: worker_count = max_limit
    except ValueError:
        worker_count = 4

    if IS_WINDOWS:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        startupinfo = None
    
    conf = load_config()
    conf.update({
        "status": "RUNNING", 
        "watch_folder": folder_sumber, 
        "price": entry_price.get(), 
        "price_video": entry_price_video.get(), 
        "fototree": entry_tree.get(),
        "worker_count": worker_count,
        "mode": mode_upload_var.get(),
        "convert_video": convert_video_var.get(),
        "rotation_dir": rotation_dir_var.get(),
        "upload_type": upload_type_var.get()
    })
    save_config(conf)
    
    ext = ".exe" if (IS_WINDOWS and getattr(sys, "frozen", False)) else ("" if getattr(sys, "frozen", False) else ".py")
    py_prefix = [] if getattr(sys, "frozen", False) else [sys.executable]
    
    scripts = [f"watcher{ext}", f"kompresor{ext}"] + [f"uploader{ext} {i}" for i in range(1, worker_count + 1)]
    
    for s in scripts:
        try:
            parts = s.split()
            program = BASE_DIR / parts[0]
            if not program.exists() and not getattr(sys, "frozen", False):
                program = BASE_DIR / (parts[0] + ".py")
                
            if not program.exists():
                messagebox.showerror("Error", f"File tidak ditemukan: {program}")
                return
                
            cmd = py_prefix + [str(program)] + parts[1:]
            
            if IS_WINDOWS:
                p = subprocess.Popen(cmd, cwd=str(BASE_DIR), startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                p = subprocess.Popen(cmd, cwd=str(BASE_DIR))
            processes.append(p)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menjalankan {s}: {e}")
            return

def stop_all(is_closing=False):
    alasan = cek_status_belum_selesai()
    if alasan:
        teks_aksi = "menutup aplikasi" if is_closing else "menghentikan sistem (Pause)"
        pesan = "Peringatan:\n" + "\n".join(alasan) + f"\n\nYakin ingin {teks_aksi}?"
        if not messagebox.askokcancel("Peringatan Sistem", pesan):
            return False 

    if is_closing:
        if STAT_FILE.exists():
            try: STAT_FILE.unlink()
            except: pass
        riwayat_file = BASE_DIR / "data" / "riwayat_kompres.txt"
        if riwayat_file.exists():
            try: riwayat_file.unlink()
            except: pass
        queue_dir = BASE_DIR / "data" / "queue"
        if queue_dir.exists():
            try:
                for item in queue_dir.iterdir():
                    if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
                    else: item.unlink()
            except: pass
        processing_dir = BASE_DIR / "data" / "processing"
        if processing_dir.exists():
            try:
                for item in processing_dir.iterdir():
                    if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
                    else: item.unlink()
            except: pass
        temp_video_dir = BASE_DIR / "data" / "temp_video"
        if temp_video_dir.exists():
            try:
                for item in temp_video_dir.iterdir():
                    if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
                    else: item.unlink()
            except: pass
        status_rotasi_file = BASE_DIR / "data" / "status_rotasi.txt"
        if status_rotasi_file.exists():
            try: status_rotasi_file.unlink()
            except: pass

    for p in processes:
        try: p.terminate()
        except: pass
    processes.clear()

    target_procs = ["watcher", "kompresor", "uploader", "python", "chrome", "Google Chrome"]
    for proc in target_procs:
        if IS_WINDOWS:
            subprocess.run(f"taskkill /F /IM {proc}.exe /T", shell=True, capture_output=True)
        else:
            subprocess.run(f"pkill -f '{proc}'", shell=True, capture_output=True)

    try:
        conf = load_config()
        conf["status"] = "IDLE"
        save_config(conf)
    except: pass
    return True

def on_closing():
    if stop_all(is_closing=True): 
        root.destroy()

def baca_statistik_live():
    if not STAT_FILE.exists(): 
        f_live, v_live = hitung_file_folder_sumber(entry_folder.get().strip())
        return "0", "0", str(f_live), str(v_live), "00:00:00", "Menghitung..."
    try:
        with open(STAT_FILE, "r", encoding="utf-8") as f: 
            stats = json.load(f)
            
        total_foto_berhasil = stats.get("total_foto", 0)
        total_video_berhasil = stats.get("total_video", 0)
        detik_foto = stats.get("total_foto_deteksi", 0)
        detik_video = stats.get("total_video_deteksi", 0)
        
        if detik_foto == 0 and detik_video == 0:
            detik_foto, detik_video = hitung_file_folder_sumber(entry_folder.get().strip())

        waktu_mulai = stats.get("waktu_mulai", 0)
        waktu_terakhir = stats.get("waktu_terakhir", waktu_mulai)
        
        waktu_str = "00:00:00"
        eta_str = "Menghitung..."
        if waktu_mulai > 0:
            if GLOBAL_IS_UPLOADING:
                durasi_detik = int(time.time() - waktu_mulai)
            else:
                durasi_detik = int(waktu_terakhir - waktu_mulai)
                
            if durasi_detik < 0: durasi_detik = 0
            jam, sisa = divmod(durasi_detik, 3600)
            menit, detik = divmod(sisa, 60)
            waktu_str = f"{jam:02d}:{menit:02d}:{detik:02d}"
            
            total_berhasil = total_foto_berhasil + total_video_berhasil
            total_deteksi = detik_foto + detik_video
            sisa_file = max(0, total_deteksi - total_berhasil)
            
            if total_berhasil > 0 and durasi_detik > 5:
                kecepatan_per_detik = total_berhasil / durasi_detik
                sisa_detik = int(sisa_file / kecepatan_per_detik) if kecepatan_per_detik > 0 else 0
                ejam, esisa = divmod(sisa_detik, 3600)
                emenit, edetik = divmod(esisa, 60)
                eta_str = f"{ejam:02d}:{emenit:02d}:{edetik:02d}"
            elif sisa_file == 0 and total_deteksi > 0:
                eta_str = "Selesai"
            else:
                eta_str = "Menghitung..."
                
        return str(total_foto_berhasil), str(total_video_berhasil), str(detik_foto), str(detik_video), waktu_str, eta_str
    except Exception:
        return "0", "0", "0", "0", "00:00:00", "Menghitung..."

def update_statistik_ui():
    f_berhasil, v_berhasil, f_deteksi, v_deteksi, waktu, eta = baca_statistik_live()
    lbl_val_foto.config(text=f"{f_berhasil} / {f_deteksi}")
    lbl_val_video.config(text=f"{v_berhasil} / {v_deteksi}")
    lbl_val_waktu.config(text=waktu)
    lbl_val_eta.config(text=eta)
    root.after(1000, update_statistik_ui)

def update_activity_ui():
    global spinner_idx, GLOBAL_IS_UPLOADING
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: config = json.load(f)
    except:
        config = {"status": "STOPPED", "worker_count": 4}
        
    if config.get("status") == "RUNNING":
        is_uploading = False
        worker_count = int(config.get("worker_count", 4))
        for i in range(1, worker_count + 1): 
            status_file = BASE_DIR / "status" / f"uploader{i}.json"
            if status_file.exists():
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        if json.load(f).get("status") == "UPLOADING":
                            is_uploading = True
                            break 
                except: pass
                    
        GLOBAL_IS_UPLOADING = is_uploading
        
        btn_login.config(state="disabled", bg="#334155", fg="#94a3b8")
        btn_logout.config(state="disabled", bg="#334155", fg="#94a3b8")
        
        if is_uploading:
            lbl_activity.config(text=f"✅ Mengunggah ({worker_count} Uploader Aktif)", fg=GREEN)
            btn_start.config(state="disabled", bg="#0e7490", text="Sistem Berjalan...")
        else:
            char = spinner_chars[spinner_idx % len(spinner_chars)]
            spinner_idx += 1
            lbl_activity.config(text=f"{char} Memproses & Menyiapkan File {char}", fg=ORANGE)
            btn_start.config(state="disabled", bg="#0e7490", text="Sistem Berjalan...")
    else:
        GLOBAL_IS_UPLOADING = False
        lbl_activity.config(text="Sistem Sedang Berhenti (Idle)", fg=TEXT_MUTED)
        btn_start.config(state="normal", bg=CYAN, text="▶ Mulai Kompres & Upload")
        btn_login.config(state="normal", bg="#2563eb", fg="#ffffff")
        btn_logout.config(state="normal", bg="#b45309", fg="#ffffff")
        
    root.after(150, update_activity_ui)

def update_batch_monitor():
    global last_batch_state
    status_file = BASE_DIR / "data" / "status_rotasi.txt"
    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as sf:
                teks_status = sf.read().strip()
                label_status_rotasi.config(text=f"🎬 {teks_status}...")
        except: pass
    else:
        label_status_rotasi.config(text="")

    current_state = []
    try:
        processing_dir = BASE_DIR / "data" / "processing"
        if processing_dir.exists():
            for d in processing_dir.iterdir():
                if d.is_dir():
                    count = len(list(d.glob("*.*")))
                    nama_rapi = d.name.replace("_U", " (Uploader ") + ")" if "_U" in d.name else d.name
                    current_state.append((f"🚀 [UPLOAD] {nama_rapi} : {count} File", CYAN))

        queue_dir = BASE_DIR / "data" / "queue"
        if queue_dir.exists():
            for d in queue_dir.iterdir():
                if d.is_dir():
                    count = len(list(d.glob("*.*")))
                    if d.name.endswith(".compressing"):
                        nama_asli = d.name.replace(".compressing", "")
                        current_state.append((f"⚙️ [MEMPROSES] {nama_asli} : {count} File", GREEN))
                    else:
                        current_state.append((f"⏳ [ANTREAN] {d.name} : {count} File", ORANGE))
                elif d.is_file() and d.suffix == ".json" and not d.name.endswith(".lock"):
                    current_state.append((f"🎫 [TIKET] {d.name} : Siap Upload", ORANGE))
    except: pass
        
    if not current_state:
        current_state.append(("Tidak ada batch dalam antrean...", TEXT_MUTED))
        
    if current_state != last_batch_state:
        list_batch.delete(0, tk.END)
        for text, color in current_state:
            list_batch.insert(tk.END, f"  {text}")
            list_batch.itemconfig(tk.END, {'fg': color})
        last_batch_state = current_state

    root.after(1000, update_batch_monitor)

root = tk.Tk()
root.withdraw() 
if check_activation(): root.deiconify()
else: sys.exit()

root.title("Fotoyu Auto Batch Uploader")
root.geometry("850x910")
root.configure(bg=BG_MAIN)
root.protocol("WM_DELETE_WINDOW", on_closing)
root.attributes("-topmost", True)

SINGLE_INSTANCE_PORT = 65432  
lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    lock_socket.bind(('127.0.0.1', SINGLE_INSTANCE_PORT))
except socket.error:
    temp_root = tk.Tk()
    temp_root.withdraw()
    messagebox.showwarning("Peringatan", "Aplikasi sudah berjalan! Anda tidak dapat membuka jendela baru.")
    temp_root.destroy()
    sys.exit(0)

upload_type_var = tk.StringVar(value=load_config().get("upload_type", "berbarengan"))
mode_upload_var = tk.StringVar(value=load_config().get("mode", "kompres"))
convert_video_var = tk.BooleanVar(value=load_config().get("convert_video", False))
rotation_dir_var = tk.StringVar(value=load_config().get("rotation_dir", "clockwise"))

header_frame = tk.Frame(root, bg=BG_PANEL, bd=1, relief="flat", highlightbackground=BORDER, highlightthickness=1)
header_frame.pack(fill=tk.X, side=tk.TOP)

tk.Label(header_frame, text="FOTOYU AUTO BATCH UPLOADER", font=("Segoe UI", 12, "bold"), bg=BG_PANEL, fg="#ffffff").pack(side=tk.LEFT, padx=20, pady=12)
tk.Label(header_frame, text="● SYSTEM ACTIVE", font=("Segoe UI", 9, "bold"), bg="#083344", fg=CYAN, padx=10, pady=2).pack(side=tk.RIGHT, padx=20, pady=12)

container = tk.Frame(root, bg=BG_MAIN)
container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

main_canvas = tk.Canvas(container, bg=BG_MAIN, highlightthickness=0)
main_scrollbar = tk.Scrollbar(container, orient="vertical", command=main_canvas.yview)

main_frame = tk.Frame(main_canvas, bg=BG_MAIN)
main_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))

canvas_window = main_canvas.create_window((0, 0), window=main_frame, anchor="nw")
main_canvas.bind("<Configure>", lambda event: main_canvas.itemconfig(canvas_window, width=event.width))
main_canvas.configure(yscrollcommand=main_scrollbar.set)

main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0), pady=20)
main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
root.bind_all("<MouseWheel>", lambda event: main_canvas.yview_scroll(int(-1*(event.delta/120)), "units"))

left_col = tk.Frame(main_frame, bg=BG_MAIN)
left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

panel_settings = tk.Frame(left_col, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1, padx=15, pady=15)
panel_settings.pack(fill=tk.BOTH, expand=True)

tk.Label(panel_settings, text="Pengaturan Integrasi", font=("Segoe UI", 10, "bold"), bg=BG_PANEL, fg=TEXT_MAIN).pack(anchor="w", pady=(0, 15))

frame_upload_type = tk.LabelFrame(panel_settings, text="Prioritas Unggah Konten", font=("Segoe UI", 9, "bold"), bg=BG_PANEL, fg=TEXT_MAIN, padx=10, pady=5)
frame_upload_type.pack(fill=tk.X, pady=(10, 15))

tk.Radiobutton(frame_upload_type, text="Berbarengan", variable=upload_type_var, value="berbarengan", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).grid(row=0, column=0, sticky="w", padx=5, pady=2)
tk.Radiobutton(frame_upload_type, text="Video Dulu", variable=upload_type_var, value="video_dulu", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).grid(row=0, column=1, sticky="w", padx=5, pady=2)
tk.Radiobutton(frame_upload_type, text="Foto Dulu", variable=upload_type_var, value="foto_dulu", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).grid(row=1, column=0, sticky="w", padx=5, pady=2)
tk.Radiobutton(frame_upload_type, text="Jangan Upload Video", variable=upload_type_var, value="jangan_video", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).grid(row=1, column=1, sticky="w", padx=5, pady=2)
tk.Radiobutton(frame_upload_type, text="Jangan Upload Foto", variable=upload_type_var, value="jangan_foto", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).grid(row=2, column=0, sticky="w", padx=5, pady=2)

tk.Label(panel_settings, text="Folder Sumber Foto", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
frame_folder = tk.Frame(panel_settings, bg=BG_PANEL)
frame_folder.pack(fill=tk.X, pady=(0, 10))
entry_folder = tk.Entry(frame_folder, font=("Segoe UI",10), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1)
entry_folder.insert(0, load_config().get("watch_folder", ""))
entry_folder.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
btn_folder = tk.Button(frame_folder, text="Pilih", bg="#1f2937", fg=TEXT_MAIN, relief="flat", cursor="hand2", command=select_folder)
btn_folder.pack(side=tk.RIGHT, padx=(5,0), ipady=1)

frame_inputs = tk.Frame(panel_settings, bg=BG_PANEL)
frame_inputs.pack(fill=tk.X, pady=(0,10))

f_harga = tk.Frame(frame_inputs, bg=BG_PANEL)
f_harga.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
tk.Label(f_harga, text="Harga Foto", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
entry_price = tk.Entry(f_harga, font=("Segoe UI",10), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1)
entry_price.insert(0, load_config().get("price", ""))
entry_price.pack(fill=tk.X, ipady=4)

f_harga_v = tk.Frame(frame_inputs, bg=BG_PANEL)
f_harga_v.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5,0))
tk.Label(f_harga_v, text="Harga Video", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
entry_price_video = tk.Entry(f_harga_v, font=("Segoe UI",10), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1)
entry_price_video.insert(0, load_config().get("price_video", ""))
entry_price_video.pack(fill=tk.X, ipady=4)

f_tree = tk.Frame(panel_settings, bg=BG_PANEL)
f_tree.pack(fill=tk.X, pady=(0,10))
tk.Label(f_tree, text="FotoTree", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
entry_tree = tk.Entry(f_tree, font=("Segoe UI",10), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1)
entry_tree.insert(0, load_config().get("fototree", ""))
entry_tree.pack(fill=tk.X, ipady=4)

chk_convert_video = tk.Checkbutton(panel_settings, text="Ubah Video Horizontal ke Vertikal (9:16)", variable=convert_video_var, bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN)
chk_convert_video.pack(anchor="w", pady=(5, 5))

frame_rotation = tk.Frame(panel_settings, bg=BG_PANEL)
frame_rotation.pack(fill=tk.X, pady=(0, 10), padx=(20, 0))
tk.Label(frame_rotation, text="Arah Putar Video:", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 2))
tk.Radiobutton(frame_rotation, text="Searah Jarum Jam", variable=rotation_dir_var, value="clockwise", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).pack(side=tk.LEFT, padx=(0, 15))
tk.Radiobutton(frame_rotation, text="Berlawanan Jarum Jam", variable=rotation_dir_var, value="counter", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).pack(side=tk.LEFT)

tk.Label(panel_settings, text="Mode Pemrosesan (Pilih Kecepatan vs Kualitas)", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w", pady=(5, 2))
frame_mode = tk.Frame(panel_settings, bg=BG_PANEL)
frame_mode.pack(fill=tk.X, pady=(0, 15))
tk.Radiobutton(frame_mode, text="Kompres (Cepat)", variable=mode_upload_var, value="kompres", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).pack(side=tk.LEFT, padx=(0, 15))
tk.Radiobutton(frame_mode, text="Langsung (Kualitas Asli)", variable=mode_upload_var, value="langsung", bg=BG_PANEL, fg=TEXT_MAIN, selectcolor=BG_INPUT, activebackground=BG_PANEL, activeforeground=CYAN).pack(side=tk.LEFT)

MAX_WORKERS_ALLOWED = get_max_allowed_workers()
tk.Label(panel_settings, text=f"Jumlah Uploader (Maks {MAX_WORKERS_ALLOWED} - Spek Terdeteksi)", font=("Segoe UI", 9), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w")
var_worker = tk.StringVar(value=str(min(int(load_config().get("worker_count", 4)), MAX_WORKERS_ALLOWED)))
spin_worker = tk.Spinbox(panel_settings, from_=1, to=MAX_WORKERS_ALLOWED, textvariable=var_worker, font=("Segoe UI",10), bg=BG_INPUT, fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat", highlightbackground=BORDER, highlightthickness=1, buttonbackground=BG_PANEL)
spin_worker.pack(fill=tk.X, pady=(0, 15), ipady=4)

tk.Label(panel_settings, text="Sistem Akun", font=("Segoe UI", 10, "bold"), bg=BG_PANEL, fg=TEXT_MAIN).pack(anchor="w", pady=(5, 5))
lbl_login = tk.Label(panel_settings, text="Status: Mengecek...", font=("Segoe UI", 9, "bold"), bg=BG_PANEL, fg=TEXT_MUTED)
lbl_login.pack(anchor="w", pady=(0, 10))

frame_btn_akun = tk.Frame(panel_settings, bg=BG_PANEL)
frame_btn_akun.pack(fill=tk.X)
btn_login = tk.Button(frame_btn_akun, text="Login Browser", bg="#2563eb", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2", command=run_login)
btn_login.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5), ipady=3)
btn_logout = tk.Button(frame_btn_akun, text="Logout / Hapus Sesi", bg="#b45309", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2", command=logout)
btn_logout.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5,0), ipady=3)

right_col = tk.Frame(main_frame, bg=BG_MAIN)
right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))

panel_control = tk.Frame(right_col, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=20)
panel_control.pack(fill=tk.BOTH, expand=True)
tk.Label(panel_control, text="KONTROL ALUR KERJA", font=("Segoe UI", 10, "bold"), bg=BG_PANEL, fg=TEXT_MUTED).pack(anchor="w", pady=(0, 15))

lbl_activity = tk.Label(panel_control, text="Sistem Sedang Berhenti (Idle)", font=("Segoe UI", 11, "bold"), bg=BG_PANEL, fg=TEXT_MUTED)
lbl_activity.pack(pady=15)

btn_start = tk.Button(panel_control, text="▶ Mulai Kompres & Upload", bg=CYAN, fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=start_all)
btn_start.pack(fill=tk.X, pady=(0, 10), ipady=6)

btn_stop = tk.Button(panel_control, text="■ Pause / Hentikan Sistem", bg=RED, fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=stop_all)
btn_stop.pack(fill=tk.X, pady=(0, 20), ipady=6)

dashboard_frame = tk.Frame(panel_control, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
dashboard_frame.pack(fill=tk.X, pady=10)

stat_f = tk.Frame(dashboard_frame, bg=BG_INPUT, pady=12)
stat_f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
tk.Label(stat_f, text="FOTO (Suk/Det)", font=("Segoe UI", 7, "bold"), bg=BG_INPUT, fg=TEXT_MUTED).pack()
lbl_val_foto = tk.Label(stat_f, text="0 / 0", font=("Segoe UI", 12, "bold"), bg=BG_INPUT, fg=GREEN)
lbl_val_foto.pack()
tk.Frame(dashboard_frame, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=10)

stat_v = tk.Frame(dashboard_frame, bg=BG_INPUT, pady=12)
stat_v.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
tk.Label(stat_v, text="VIDEO (Suk/Det)", font=("Segoe UI", 7, "bold"), bg=BG_INPUT, fg=TEXT_MUTED).pack()
lbl_val_video = tk.Label(stat_v, text="0 / 0", font=("Segoe UI", 12, "bold"), bg=BG_INPUT, fg=CYAN)
lbl_val_video.pack()
tk.Frame(dashboard_frame, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=10)

stat_w = tk.Frame(dashboard_frame, bg=BG_INPUT, pady=12)
stat_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
tk.Label(stat_w, text="WAKTU", font=("Segoe UI", 7, "bold"), bg=BG_INPUT, fg=TEXT_MUTED).pack()
lbl_val_waktu = tk.Label(stat_w, text="00:00:00", font=("Segoe UI", 12, "bold"), bg=BG_INPUT, fg=TEXT_MAIN)
lbl_val_waktu.pack()
tk.Frame(dashboard_frame, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=10)

stat_e = tk.Frame(dashboard_frame, bg=BG_INPUT, pady=12)
stat_e.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
tk.Label(stat_e, text="ESTIMASI (ETA)", font=("Segoe UI", 7, "bold"), bg=BG_INPUT, fg=TEXT_MUTED).pack()
lbl_val_eta = tk.Label(stat_e, text="Menghitung", font=("Segoe UI", 12, "bold"), bg=BG_INPUT, fg=ORANGE)
lbl_val_eta.pack()

tk.Label(right_col, text="MONITOR STATUS BATCH", font=("Segoe UI", 9, "bold"), bg=BG_MAIN, fg=TEXT_MUTED).pack(anchor="w", pady=(10, 5))
label_status_rotasi = ttk.Label(right_col, text="", foreground=CYAN, font=("Segoe UI", 9, "bold"))
label_status_rotasi.pack(anchor="w", pady=(0, 5))

frame_list = tk.Frame(right_col, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
frame_list.pack(fill=tk.BOTH, expand=True)
scrollbar = tk.Scrollbar(frame_list)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
list_batch = tk.Listbox(frame_list, bg=BG_INPUT, fg=TEXT_MAIN, font=("Consolas", 10), relief="flat", highlightthickness=0, yscrollcommand=scrollbar.set, selectbackground="#1f2937")
list_batch.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
scrollbar.config(command=list_batch.yview)

check_login_status_loop()
update_activity_ui()
update_statistik_ui() 
update_batch_monitor() 
root.mainloop()