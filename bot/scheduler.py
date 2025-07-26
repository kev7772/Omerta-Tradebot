import schedule
import time
from datetime import datetime
from live_logger import write_history
from learn_scheduler import evaluate_pending_learnings

def job_write_history():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] ⏰ Kursdaten-Snapshot läuft...")
    try:
        write_history()
    except Exception as e:
        print(f"[{now}] ❌ Fehler beim Logging: {e}")

def job_learn():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 🧠 Bewertungsjob läuft...")
    try:
        evaluate_pending_learnings()
    except Exception as e:
        print(f"[{now}] ❌ Fehler beim Lernen: {e}")

def run_scheduler():
    # Jeden Tag um 00:01 History loggen
    schedule.every().day.at("00:01").do(job_write_history)
    # Jeden Tag um 00:10 automatisch lernen
    schedule.every().day.at("00:10").do(job_learn)

    print("🔄 Scheduler läuft dauerhaft...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
