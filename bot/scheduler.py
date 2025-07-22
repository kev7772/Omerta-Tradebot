# scheduler.py
import schedule
import time
from live_logger import write_history
from datetime import datetime

def job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] ⏰ Kursdaten-Snapshot läuft...")
    try:
        write_history()
    except Exception as e:
        print(f"[{now}] ❌ Fehler beim Logging: {e}")

schedule.every().day.at("10:00").do(job)

if __name__ == "__main__":
    print("🔄 Scheduler läuft...")
    while True:
        schedule.run_pending()
        time.sleep(60)
