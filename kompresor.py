from PIL import Image, ImageOps
import os
import time
import sys
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
from datetime import datetime
import json
import psutil 

IS_WINDOWS = sys.platform == "win32"
EXE_EXT = ".exe" if IS_WINDOWS else ""

def get_optimal_workers():
    cpu_count = os.cpu_count() or 4
    return max(4, cpu_count) 

MAX_WORKERS = get_optimal_workers()

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

STATUS_FILE = BASE_DIR / "data" / "status_rotasi.txt"
CONFIG_FILE = BASE_DIR / "config.json"
QUEUE_FOLDER = BASE_DIR / "data" / "queue"
PROCESSING_FOLDER = BASE_DIR / "data" / "processing"
QUEUE_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSING_FOLDER.mkdir(parents=True, exist_ok=True)
RIWAYAT_FILE = BASE_DIR / "data" / "riwayat_kompres.txt"

def load_riwayat():
    if not RIWAYAT_FILE.exists(): 
        return set()
    with open(RIWAYAT_FILE, "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

def save_riwayat(filenames):
    with open(RIWAYAT_FILE, "a", encoding="utf-8") as f:
        for name in filenames:
            f.write(name + "\n")

def is_file_ready(file_path):
    try:
        if os.path.getsize(file_path) == 0: return False
        with open(file_path, 'rb'): pass 
        return True
    except Exception:
        return False

def cek_apakah_video_vertikal(video_path):
    try:
        ffprobe_path = BASE_DIR / f"ffprobe{EXE_EXT}"
        eksekutor = str(ffprobe_path) if ffprobe_path.exists() else "ffprobe"
        
        cmd = [eksekutor, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:stream_tags=rotate", "-of", "json", str(video_path)]
        
        if IS_WINDOWS:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
        info = json.loads(result.stdout)
        stream = info['streams'][0]
        
        width = int(stream.get('width', 0))
        height = int(stream.get('height', 0))
        tags = stream.get('tags', {})
        rotate = int(tags.get('rotate', 0))
        
        if rotate == 90 or rotate == 270:
            width, height = height, width
            
        return height > width
    except Exception as e:
        print(f"Gagal mengecek dimensi {video_path}, asumsikan horizontal. Error: {e}")
        return False 

def proses_konversi_video_vertikal(input_path_str, output_folder, rotation_dir="clockwise", index_ke=1):
    input_path = Path(input_path_str)
    
    if cek_apakah_video_vertikal(input_path):
        print(f"⏩ Lewati rotasi: {input_path.name} sudah vertikal!")
        return str(input_path) 
        
    output_path = output_folder / input_path.name
    if output_path.exists():
        return str(output_path)
        
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as sf:
            sf.write(f"Tunggu, sedang rotate video {index_ke}/5: {input_path.name}")

        transpose_val = "1" if rotation_dir == "clockwise" else "2"
        
        ffmpeg_path = BASE_DIR / f"ffmpeg{EXE_EXT}"
        eksekutor_ffmpeg = str(ffmpeg_path) if ffmpeg_path.exists() else "ffmpeg"
            
        cmd = [eksekutor_ffmpeg, "-y", "-i", str(input_path), "-vf", f"transpose={transpose_val},crop=ih*(9/16):ih", "-c:a", "copy", str(output_path)]
        
        if IS_WINDOWS:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        
        if STATUS_FILE.exists(): STATUS_FILE.unlink()
        return str(output_path)
    except Exception as e:
        print(f"Gagal mengonversi video {input_path.name}: {e}")
        if STATUS_FILE.exists(): STATUS_FILE.unlink()
        return str(input_path)
    
def proses_foto_kompres(data):
    input_path_str, temp_output_folder = data
    input_path = Path(input_path_str)
    output_path = temp_output_folder / input_path.name
    try:
        with Image.open(input_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            if img.width > 1280 or img.height > 1280:
                img.thumbnail((1280, 1280))
            img.save(output_path, "JPEG", quality=85, optimize=True, subsampling=0)
        return input_path.name
    except Exception as e:
        print(f"Gagal mengompres foto {input_path.name}: {e}")
        return None

def main():
    print("PROSESOR MULTIMEDIA BERJALAN...")
    LAST_COUNT_FOTO = 0
    LAST_CHANGE_FOTO = time.time()
    LAST_COUNT_VIDEO = 0
    LAST_CHANGE_VIDEO = time.time()
    
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        riwayat_kompres = load_riwayat()
        stable_foto = []
        stable_video = []
        stable_foto_langsung = [] 
        
        while True:
            try:
                if not CONFIG_FILE.exists():
                    time.sleep(5)
                    continue
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if config.get("status") != "RUNNING":
                    time.sleep(2)
                    continue

                current_mode = config.get("mode", "kompres") 
                upload_type = config.get("upload_type", "berbarengan")
                watch_folder_str = config.get("watch_folder")
                if not watch_folder_str or not Path(watch_folder_str).exists():
                    time.sleep(5)
                    continue
                    
                rotation_dir = config.get("rotation_dir", "clockwise")
                watch_path = str(Path(watch_folder_str))
                boleh_proses_video = True
                boleh_proses_foto = True
                
                if upload_type == "jangan_video": boleh_proses_video = False
                elif upload_type == "jangan_foto": boleh_proses_foto = False 

                dalam_antrean_v = {item[1] for item in stable_video}
                dalam_antrean_f = {item[1] for item in stable_foto}
                dalam_antrean_fl = {item[1] for item in stable_foto_langsung}

                def eksekusi_video(paksa_semua=False):
                    nonlocal stable_video, LAST_COUNT_VIDEO, LAST_CHANGE_VIDEO
                    
                    while len(stable_video) >= 5:
                        chunk = stable_video[:5]
                        daftar_path_video = [item[0] for item in chunk]
                        daftar_unik_video = [item[1] for item in chunk]
                        batch_name_v = datetime.now().strftime("video_%Y%m%d_%H%M%S_%f")
                        ticket_path = QUEUE_FOLDER / f"{batch_name_v}.json"
                        
                        with open(ticket_path, "w", encoding="utf-8") as tf:
                            json.dump(daftar_path_video, tf)
                            
                        try: save_riwayat(daftar_unik_video)
                        except: pass
                        riwayat_kompres.update(daftar_unik_video)
                        del stable_video[:5]
                        print(f"🎫 Tiket Batch Video berhasil dibuat berisi {len(daftar_path_video)} file video!")

                    current_count = len(stable_video)
                    if current_count != LAST_COUNT_VIDEO:
                        LAST_COUNT_VIDEO = current_count
                        LAST_CHANGE_VIDEO = time.time()
                    
                    idle_seconds = time.time() - LAST_CHANGE_VIDEO
                    if paksa_semua or (current_count > 0 and idle_seconds >= 4.0):
                        chunk = stable_video[:current_count]
                        daftar_path_video = [item[0] for item in chunk]
                        daftar_unik_video = [item[1] for item in chunk]
                        batch_name_v = datetime.now().strftime("video_%Y%m%d_%H%M%S_%f")
                        ticket_path = QUEUE_FOLDER / f"{batch_name_v}.json"
                        
                        with open(ticket_path, "w", encoding="utf-8") as tf:
                            json.dump(daftar_path_video, tf)
                            
                        try: save_riwayat(daftar_unik_video)
                        except: pass
                        riwayat_kompres.update(daftar_unik_video)
                        stable_video.clear()
                        LAST_COUNT_VIDEO = 0
                        LAST_CHANGE_VIDEO = time.time()
                        print(f"🎫 Tiket Sisa Video Terakhir berhasil dibuat berisi {len(daftar_path_video)} file video!")

                for root, dirs, files in os.walk(watch_path):
                    if 'foto_asli' in dirs: dirs.remove('foto_asli') 
                    root_path = Path(root)
                    parent_name = root_path.name
                    
                    for file_name in files:
                        file_lower = file_name.lower()
                        if file_lower.endswith(('.mp4', '.mov')) and boleh_proses_video:
                            unik_v = f"video_{parent_name}_{file_name}" if parent_name else f"video_{file_name}"
                            if unik_v not in riwayat_kompres and unik_v not in dalam_antrean_v:
                                file_path = root_path / file_name
                                if is_file_ready(file_path):
                                    final_video_path = str(file_path)
                                    if config.get("convert_video", False):
                                        temp_v_folder = BASE_DIR / "data" / "temp_video"
                                        temp_v_folder.mkdir(parents=True, exist_ok=True)
                                        index_ke = len(stable_video) + 1
                                        final_video_path = proses_konversi_video_vertikal(str(file_path), temp_v_folder, rotation_dir, index_ke)
                                    stable_video.append((final_video_path, unik_v))
                                    if len(stable_video) >= 5: eksekusi_video()

                        elif boleh_proses_foto and file_lower.endswith(('.jpg', '.jpeg', '.png')):
                            if current_mode == "langsung":
                                unik_foto_L = f"foto_langsung_{parent_name}_{file_name}" if parent_name else f"foto_langsung_{file_name}"
                                if unik_foto_L not in riwayat_kompres and unik_foto_L not in dalam_antrean_fl:
                                    file_path = root_path / file_name
                                    if is_file_ready(file_path):
                                        stable_foto_langsung.append((str(file_path), unik_foto_L))
                            elif current_mode == "kompres":
                                nama_unik = f"{parent_name}_{file_name}" if parent_name else file_name
                                if nama_unik not in riwayat_kompres and nama_unik not in dalam_antrean_f:
                                    file_path = root_path / file_name
                                    if is_file_ready(file_path):
                                        stable_foto.append((str(file_path), nama_unik))

                def eksekusi_foto():
                    nonlocal LAST_COUNT_FOTO, LAST_CHANGE_FOTO
                    if len(stable_foto_langsung) > 0:
                        target_batch = config.get("batch", 100)
                        batch_items = stable_foto_langsung[:target_batch]
                        ticket_path = QUEUE_FOLDER / f"foto_langsung_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
                        daftar_path_asli = [item[0] for item in batch_items]
                        with open(ticket_path, "w", encoding="utf-8") as tf:
                            json.dump(daftar_path_asli, tf)
                        berhasil_ids = [item[1] for item in batch_items]
                        try: save_riwayat(berhasil_ids)
                        except: pass
                        riwayat_kompres.update(berhasil_ids)
                        del stable_foto_langsung[:len(batch_items)]

                    current_count_foto = len(stable_foto)
                    if current_count_foto != LAST_COUNT_FOTO:
                        LAST_COUNT_FOTO = current_count_foto
                        LAST_CHANGE_FOTO = time.time()

                    idle_seconds = time.time() - LAST_CHANGE_FOTO
                    target_batch = config.get("batch", 100)
                    
                    if current_count_foto >= target_batch or (current_count_foto > 0 and idle_seconds >= 5.0):
                        files_to_process = stable_foto[:target_batch]
                        batch_name = datetime.now().strftime("batch_%Y%m%d_%H%M%S")
                        batch_folder_temp = QUEUE_FOLDER / (batch_name + ".compressing")
                        batch_folder_final = QUEUE_FOLDER / batch_name
                        
                        if batch_folder_temp.exists(): shutil.rmtree(batch_folder_temp, ignore_errors=True)
                        batch_folder_temp.mkdir(parents=True, exist_ok=True)
                        
                        tasks = [(f[0], batch_folder_temp) for f in files_to_process]
                        berhasil_diproses = []
                        hasil = executor.map(proses_foto_kompres, tasks, chunksize=8)
                        for idx, nama_file in enumerate(hasil):
                            if nama_file: berhasil_diproses.append(files_to_process[idx][1])
                        
                        if berhasil_diproses:
                            try: save_riwayat(berhasil_diproses)
                            except: pass
                            riwayat_kompres.update(berhasil_diproses)
                            if batch_folder_temp.exists() and any(batch_folder_temp.iterdir()):
                                if batch_folder_final.exists(): shutil.rmtree(batch_folder_final, ignore_errors=True)
                                batch_folder_temp.rename(batch_folder_final)
                            else:
                                shutil.rmtree(batch_folder_temp, ignore_errors=True)
                        else:
                            shutil.rmtree(batch_folder_temp, ignore_errors=True)
                        
                        del stable_foto[:len(files_to_process)]
                        LAST_COUNT_FOTO = 0
                        LAST_CHANGE_FOTO = time.time()

                if upload_type == "foto_dulu":
                    eksekusi_foto()
                    eksekusi_video()
                elif upload_type == "video_dulu":
                    eksekusi_video()
                    eksekusi_foto()
                else: 
                    eksekusi_video()
                    eksekusi_foto()

                time.sleep(1)

            except Exception as e:
                time.sleep(5)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        if PROCESSING_FOLDER.exists():
            for item in PROCESSING_FOLDER.iterdir():
                try:
                    if item.is_dir(): shutil.rmtree(item, ignore_errors=True)
                    else: item.unlink()
                except: pass
    except: pass
    main()