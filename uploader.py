import json
import shutil
import time
from difflib import SequenceMatcher
import sys
from PIL import Image
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_utils import launch_browser
import os

uploader_id = sys.argv[1] if len(sys.argv) > 1 else "1"

if getattr(sys, "frozen", False): 
    BASE_DIR = Path(sys.executable).parent
else: 
    BASE_DIR = Path(__file__).parent

STATUS_FILE = BASE_DIR / "status" / f"uploader{uploader_id}.json"
STATUS_FILE.parent.mkdir(exist_ok=True)   

STAT_FILE = BASE_DIR / "data" / "total_stats.json"

BROWSER_DATA_DIR = BASE_DIR / f"browser-data-u{uploader_id}"
CONFIG_FILE = BASE_DIR / "config.json"
QUEUE_FOLDER = BASE_DIR / "data" / "queue"
UPLOADED_FOLDER = BASE_DIR / "data" / "uploaded"

UPLOADED_FOLDER.mkdir(exist_ok=True)
BROWSER_DATA_DIR.mkdir(exist_ok=True)

print(f"UPLOADER {uploader_id} BERJALAN (Direct Queue & Anti-Double)...")

def update_global_stats(jumlah_baru, is_video=False):
    for _ in range(10):
        try:
            now = time.time()
            data = {"total_foto": 0, "total_video": 0, "waktu_mulai": now, "waktu_terakhir": now}
            
            if STAT_FILE.exists():
                with open(STAT_FILE, "r", encoding="utf-8") as f: 
                    data = json.load(f)
            
            if "total_video" not in data: data["total_video"] = 0

            if is_video: data["total_video"] += jumlah_baru
            else: data["total_foto"] += jumlah_baru
                
            data["waktu_terakhir"] = now 
            with open(STAT_FILE, "w", encoding="utf-8") as f: 
                json.dump(data, f)
            return data
        except Exception:
            time.sleep(0.5) 
    return None

def get_global_stats():
    if STAT_FILE.exists():
        try:
            with open(STAT_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    now = time.time()
    return {"total_video": 0, "total_foto": 0, "waktu_mulai": now, "waktu_terakhir": now}

def is_file_corrupt(file_path):
    try:
        with Image.open(file_path) as img: img.verify() 
        return False
    except: return True 

def recovery_tertindal():
    if not QUEUE_FOLDER.exists(): return
    for lock_file in QUEUE_FOLDER.glob("*.lock"):
        try:
            if time.time() - lock_file.stat().st_mtime > 300:
                lock_file.unlink()
        except: pass

recovery_tertindal() 

def get_next_batch():
    all_items = []
    if not QUEUE_FOLDER.exists(): return None
        
    for f in QUEUE_FOLDER.iterdir():
        if f.is_dir() and not f.name.endswith(".compressing"): all_items.append(f)
        elif f.is_file() and f.suffix == ".json" and not f.name.endswith(".lock"): all_items.append(f)

    if not all_items: return None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: cfg = json.load(f)
        upload_type = cfg.get("upload_type", "berbarengan")
    except:
        upload_type = "berbarengan"

    if upload_type == "video_dulu": all_items.sort(key=lambda x: 0 if x.is_file() else 1)
    elif upload_type == "foto_dulu": all_items.sort(key=lambda x: 0 if x.is_dir() else 1)
        
    for item in all_items:
        lock_file = QUEUE_FOLDER / f"{item.name}.lock"
        if lock_file.exists():
            try:
                if time.time() - lock_file.stat().st_mtime > 600: lock_file.unlink()
                else: continue 
            except: continue
        try:
            with open(lock_file, "x") as f: f.write(uploader_id)
        except: continue 
        return item
    return None

waktu_mulai_idle = 0
laporan_sudah_dicetak = False

while True:
    batch_path = None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f: config = json.load(f)

        if config.get("status") != "RUNNING":
            STATUS_FILE.write_text(json.dumps({"status": "STOPPED"}))
            waktu_mulai_idle = 0
            laporan_sudah_dicetak = False
            time.sleep(2)
            continue

        batch_path = get_next_batch()

        if batch_path is None:
            stats = get_global_stats()
            if stats["total_foto"] > 0 and not laporan_sudah_dicetak:
                if waktu_mulai_idle == 0: waktu_mulai_idle = time.time()
                elif (time.time() - waktu_mulai_idle) >= 10:
                    durasi_detik = int(stats.get("waktu_terakhir", time.time()) - stats["waktu_mulai"])
                    if durasi_detik < 0: durasi_detik = 0
                    jam, sisa = divmod(durasi_detik, 3600)
                    menit, detik = divmod(sisa, 60)
                    print(f"\n{'='*55}\n🎉 TOTAL KESELURUHAN SISTEM (U1 - U8)\nTotal Item : {stats['total_foto']}\nWaktu Total : {jam:02d}:{menit:02d}:{detik:02d}\n{'='*55}\n")
                    laporan_sudah_dicetak = True
            
            STATUS_FILE.write_text(json.dumps({"status": "IDLE"}))
            time.sleep(2)
            continue

        waktu_mulai_idle = 0 
        laporan_sudah_dicetak = False 
        STATUS_FILE.write_text(json.dumps({"status": "UPLOADING"}))
        
        is_ticket = batch_path.is_file() and batch_path.suffix == ".json"
        is_video_ticket = False
        files = []
        
        if is_ticket:
            if "video_" in batch_path.name: is_video_ticket = True
            else: is_video_ticket = False
                
            with open(batch_path, "r", encoding="utf-8") as tf: raw_paths = json.load(tf)
            files = [str(p) for p in raw_paths if Path(p).exists()]
        else:
            files = [str(f) for f in batch_path.glob("*.*") if f.suffix.lower() in ['.jpg', '.jpeg', '.png']]
        
        if len(files) == 0: 
            try:
                lock_file = QUEUE_FOLDER / f"{batch_path.name}.lock"
                if lock_file.exists(): lock_file.unlink()
                if batch_path.is_file(): batch_path.unlink()
                else: shutil.rmtree(batch_path, ignore_errors=True)
            except: pass
            continue

        valid_files = [f for f in files if is_video_ticket or not is_file_corrupt(f)]
        if len(valid_files) == 0:
            try:
                lock_file = QUEUE_FOLDER / f"{batch_path.name}.lock"
                if lock_file.exists(): lock_file.unlink()
                if batch_path.is_file(): batch_path.unlink()
                else: shutil.rmtree(batch_path, ignore_errors=True)
            except: pass
            STATUS_FILE.write_text(json.dumps({"status": "IDLE"}))
            continue 

        PRICE = str(config.get("price_video", config["price"])) if is_video_ticket else str(config["price"])
        FOTOTREE = config["fototree"]

        with sync_playwright() as p:
            context = launch_browser(p, user_data_dir=BROWSER_DATA_DIR, headless=False, args=["--disable-dev-shm-usage"])
            page = context.pages[0] if len(context.pages) > 0 else context.new_page()
            
            def execute_upload_step(attempt_mode=1):
                page.goto("https://www.fotoyu.com/upload", wait_until="domcontentloaded")
                
                if is_video_ticket:
                    print(f"[U{uploader_id}] Mengunggah {len(valid_files)} Video ke Pratinjau...")
                    video_input = page.locator('div[class*="GiftShopUploadDropzoneVideo"] input[type="file"]')
                    video_input.wait_for(state="attached", timeout=10000)
                    video_input.set_input_files(valid_files)
                else:
                    print(f"[U{uploader_id}] Mengunggah {len(valid_files)} Foto ke Pratinjau...")
                    foto_input = page.locator('div[class*="GiftShopUploadDropzoneBulk"] input[type="file"]')
                    foto_input.wait_for(state="attached", timeout=10000)
                    foto_input.set_input_files(valid_files)

                max_recheck = 15 
                for _ in range(max_recheck):
                    try:
                        popup_loading = page.locator("text=Memuat Konten")
                        price_check = page.locator('input[name="price"]')
                        if price_check.count() > 0 and price_check.is_enabled(): break 

                        dropzone_box = page.locator('div[class*="GiftShopUploadDropzoneVideo"]') if is_video_ticket else page.locator('div[class*="GiftShopUploadDropzoneBulk"]')
                            
                        if dropzone_box.count() > 0 and popup_loading.count() == 0:
                            if price_check.count() == 0:
                                print(f"[U{uploader_id}] ⚠️ Terdeteksi halaman ter-reset! Memasukkan ulang...")
                                if is_video_ticket: video_input.set_input_files(valid_files)
                                else: foto_input.set_input_files(valid_files)
                                page.wait_for_timeout(3000)
                    except: pass
                    time.sleep(2)

                while True:
                    try:
                        price_input = page.locator('input[name="price"]')
                        if price_input.count() > 0 and price_input.is_enabled(): break
                    except: raise Exception("BROWSER CLOSED")
                    time.sleep(2)
                price_input.fill(PRICE)

                while True:
                    try:
                        tag_input = page.locator('input[name="tagName"]')
                        if tag_input.count() > 0: break
                    except: raise Exception("BROWSER CLOSED")
                    time.sleep(1)

                current_tag = tag_input.input_value().strip()
                target_tag = FOTOTREE.strip()

                if current_tag.lower() != target_tag.lower():
                    fototree_ditemukan = False
                    while not fototree_ditemukan:
                        try:
                            tag_input.click()
                            tag_input.press("Control+A")
                            tag_input.press("Backspace")
                            for ch in FOTOTREE: tag_input.type(ch, delay=30)
                            page.wait_for_timeout(2000) 
                            
                            items = page.locator('div[data-testid="list"] p')
                            best_score, best_index = 0, -1
                            target = FOTOTREE.lower().strip()

                            for i in range(items.count()):
                                text = items.nth(i).inner_text().strip()
                                if "kami tidak dapat menemukan" in text.lower(): continue
                                score = SequenceMatcher(None, target, text.lower()).ratio()
                                if score > best_score:
                                    best_score = score
                                    best_index = i

                            if best_score >= 0.95: 
                                items.nth(best_index).click()
                                fototree_ditemukan = True 
                            else:
                                page.wait_for_timeout(1000) 
                        except: raise Exception("ERROR SAAT KETIK FOTOTREE")

                page.wait_for_timeout(2000)
                if attempt_mode == 1:
                    submit_btn = page.locator('div[data-testid="button"][label="Unggah"]')
                    if submit_btn.count() > 0: submit_btn.first.click()
                    else: page.locator('div[data-testid="button"]', has_text="Unggah").first.click()
                else:
                    page.evaluate("""
                        () => {
                            const divs = Array.from(document.querySelectorAll('div[data-testid="button"]'));
                            const btn = divs.find(d => d.innerText && d.innerText.includes('Unggah') && !d.innerText.includes('Upgrade'));
                            if (btn) { btn.click(); } else { const anyDiv = divs.find(d => d.innerText && d.innerText.includes('Unggah')); if (anyDiv) anyDiv.click(); }
                        }
                    """)

            execute_upload_step(attempt_mode=1)
            upgrade_occurred = False
            retry_count = 0
            
            while True:
                if page.is_closed(): raise Exception("BROWSER CLOSED")
                current_url = page.url.lower()
                
                if "upgrade" in current_url:
                    upgrade_occurred = True
                    break
                
                if "upload" not in current_url:
                    break
                
                try:
                    body_text = page.locator("body").inner_text().lower()
                    if "diunggah! tetapi" in body_text or "terdeteksi sebagai duplikat" in body_text: break
                    if page.get_by_text("Ulangi", exact=True).count() > 0 or "gagal diunggah" in body_text:
                        retry_count += 1
                        try: page.get_by_text("Ulangi").click()
                        except: pass
                        if retry_count >= 3: raise Exception("UPLOAD GAGAL 3 KALI")
                        time.sleep(2)
                        continue
                except: pass
                time.sleep(1.5)

            if upgrade_occurred:
                execute_upload_step(attempt_mode=2)
                while True:
                    if page.is_closed(): raise Exception("BROWSER CLOSED")
                    current_url = page.url.lower()
                    if "upgrade" in current_url: raise Exception("REDIRECT UPGRADE")
                    if "upload" not in current_url: break
                    try:
                        body_text = page.locator("body").inner_text().lower()
                        if "diunggah! tetapi" in body_text or "terdeteksi sebagai duplikat" in body_text: break
                    except: pass
                    time.sleep(1.5)

            context.close()

        update_global_stats(len(valid_files), is_video=is_video_ticket)
        time.sleep(2)

        for f in valid_files:
            try:
                file_target = Path(f)
                if "data" in file_target.parts and file_target.exists(): file_target.unlink() 
            except: pass

        try:
            lock_file = QUEUE_FOLDER / f"{batch_path.name}.lock"
            if lock_file.exists(): lock_file.unlink()
            if batch_path.exists():
                if batch_path.is_file(): batch_path.unlink()  
                else: shutil.rmtree(batch_path, ignore_errors=True) 
        except: pass
        
        STATUS_FILE.write_text(json.dumps({"status": "IDLE"}))

    except Exception as e:
        try:
            if 'context' in locals(): context.close()
        except: pass

        try:
            if batch_path is not None:
                lock_file = QUEUE_FOLDER / f"{batch_path.name}.lock"
                if lock_file.exists(): lock_file.unlink()
        except: pass
        
        STATUS_FILE.write_text(json.dumps({"status": "IDLE"}))
        time.sleep(10)