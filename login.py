import json
from playwright.sync_api import sync_playwright
from pathlib import Path
import time
import shutil
import sys
from browser_utils import launch_browser

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

def sync_login_sessions():
    print("Menyinkronkan sesi ke uploader 1-8...")
    sumber = BASE_DIR / "browser-data"
    if sumber.exists() and any(sumber.iterdir()):
        for i in range(1, 9):
            target = BASE_DIR / f"browser-data-u{i}"
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(sumber, target)
        print("Sesi berhasil disalin ke uploader 1-8!")

with sync_playwright() as p:
    browser = launch_browser(
        p,
        user_data_dir=BASE_DIR / "browser-data",
        headless=False
    )
    page = browser.new_page()
    page.goto("https://www.fotoyu.com/login")

    print("Menunggu login...")
    while True:
        try:
            nanti_saja = page.get_by_role("button", name="Nanti Saja")
            if nanti_saja.is_visible():
                nanti_saja.click()
                time.sleep(2)
            
            if "login" not in page.url.lower():
                with open(BASE_DIR / "login_status.json", "w") as f:
                    json.dump({"logged_in": True}, f)
                
                browser.close()
                sync_login_sessions()
                break
        except:
            pass
        time.sleep(1)