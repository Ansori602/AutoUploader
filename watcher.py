import time

def main():
    print("WATCHER (DINONAKTIFKAN SESUAI REQUEST) BERJALAN DALAM MODE STANDBY...")
    while True:
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            break
        except Exception:
            pass

if __name__ == "__main__":
    main()