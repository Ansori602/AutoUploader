from pathlib import Path
import os
import shutil
import platform
import webbrowser
import tkinter as tk
from tkinter import messagebox

def is_chrome_installed():
    """Mencari lokasi Google Chrome"""
    chrome = shutil.which("google-chrome") or shutil.which("chrome")
    if chrome: return chrome

    system = platform.system()
    locations = []
    if system == "Windows":
        locations = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    elif system == "Darwin": # macOS
        locations = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        ]
    else:
        locations = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chrome"]

    for path in locations:
        if Path(path).exists(): return path
    return None

def is_edge_installed():
    """Mencari lokasi Microsoft Edge"""
    edge = shutil.which("msedge") or shutil.which("microsoft-edge")
    if edge: return edge

    system = platform.system()
    locations = []
    if system == "Windows":
        locations = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")
        ]
    elif system == "Darwin": # macOS
        locations = ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    else:
        locations = ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"]

    for path in locations:
        if Path(path).exists(): return path
    return None

def prompt_install_browser():
    """Menampilkan Pop-up GUI jika Browser tidak ada"""
    root = tk.Tk()
    root.withdraw() # Sembunyikan jendela utama tkinter
    root.attributes("-topmost", True) # Pastikan pop-up muncul di paling depan
    
    pesan = (
        "Sistem tidak dapat menemukan Google Chrome atau Microsoft Edge di komputer ini.\n\n"
        "Aplikasi ini mewajibkan adanya Google Chrome untuk berjalan.\n"
        "Apakah Anda ingin membuka halaman unduhan Google Chrome sekarang?"
    )
    
    jawaban = messagebox.askyesno("Browser Tidak Ditemukan", pesan)
    if jawaban:
        webbrowser.open("https://www.google.com/chrome/")
        
    root.destroy()
    raise FileNotFoundError("Browser yang didukung (Chrome/Edge) tidak ditemukan.")

def launch_browser(playwright, user_data_dir, **kwargs):
    # 1. Cek Google Chrome
    chrome_path = is_chrome_installed()
    if chrome_path:
        print(f"Browser digunakan: Google Chrome ({chrome_path})")
        return playwright.chromium.launch_persistent_context(
            executable_path=chrome_path,
            user_data_dir=str(user_data_dir),
            **kwargs
        )
    
    # 2. Cek Microsoft Edge
    edge_path = is_edge_installed()
    if edge_path:
        print(f"Browser digunakan: Microsoft Edge ({edge_path})")
        return playwright.chromium.launch_persistent_context(
            executable_path=edge_path,
            user_data_dir=str(user_data_dir),
            **kwargs
        )

    # 3. Jika benar-benar tidak ada
    print("Browser tidak ditemukan. Menampilkan pop-up peringatan...")
    prompt_install_browser()

def browser_available():
    return is_chrome_installed() is not None or is_edge_installed() is not None