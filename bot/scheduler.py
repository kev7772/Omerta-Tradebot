# scheduler.py
import schedule
import time
from live_logger import write_history
from datetime import datetime

def job():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] ⏰ Täglicher Kurs-Log gestartet...")
    try:
        write_history()
        log_msg = f"[{now}] ✅ Kursdaten erfolgreich gespeichert.\n"
    except Exception as e:
        log_msg = f"[{now}] ❌ Fehler beim Kurs-Log: {e}\n"
    with open("scheduler_log.txt", "a") as f:
        f.write(log_msg)

schedule.every().day.at("10:00").do(job)

if __name__ == "__main__":
    print("🔄 Scheduler läuft im Hintergrund... (CTRL+C zum Stoppen)")
    while True:
        schedule.run_pending()
        time.sleep(60)
