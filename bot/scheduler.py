import schedule
import time
from live_logger import write_history
from datetime import datetime
from learn_scheduler import evaluate_pending_learnings
import schedule
import time
from live_logger import write_history
from learn_scheduler import evaluate_pending_learnings  # falls aktiv

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

def run_scheduler():
    schedule.every().day.at("00:01").do(write_history)
    schedule.every().day.at("00:10").do(evaluate_pending_learnings)

    while True:
        schedule.run_pending()
        time.sleep(60)

def run_scheduler():
    schedule.every().day.at("00:01").do(write_history)
    schedule.every().day.at("00:10").do(evaluate_pending_learnings)
