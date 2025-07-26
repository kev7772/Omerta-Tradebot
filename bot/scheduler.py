import schedule
import time
from datetime import datetime
from live_logger import write_history
from learn_scheduler import evaluate_pending_learnings
from simulator import run_simulation
from telebot import TeleBot  # ✅ passend zu deinem Bot-System
import os

# Telegram Setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
tg_bot = Bot(BOT_TOKEN)

def notify_admin(text):
    try:
        tg_bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        print("❌ Telegram-Fehler:", e)

def job_write_history():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] ⏰ Kursdaten-Snapshot läuft...")
    try:
        write_history()
        notify_admin("📊 History-Logging erfolgreich.")
    except Exception as e:
        print(f"[{now}] ❌ Fehler beim Logging: {e}")
        notify_admin(f"❌ Fehler beim Kurs-Logging: {str(e)}")

def job_learn():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 🧠 Bewertungsjob läuft...")
    try:
        result = evaluate_pending_learnings()
        if result:
            text = "📈 Lernbewertung abgeschlossen:\n"
            for r in result:
                emoji = "✅" if r["success"] > 0 else "❌"
                text += f"{emoji} {r['coin']} ({r['date']}) → {r['success']} %\n"
        else:
            text = "📉 Keine offenen Lernbewertungen vorhanden."
        notify_admin(text)
    except Exception as e:
        print(f"[{now}] ❌ Fehler beim Lernen: {e}")
        notify_admin(f"❌ Fehler beim Lernen: {str(e)}")

def job_simulation():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] 🧪 Simulation läuft...")
    try:
        run_simulation()
        notify_admin("🧪 Simulation erfolgreich abgeschlossen.")
    except Exception as e:
        print(f"[{now}] ❌ Fehler bei Simulation: {e}")
        notify_admin(f"❌ Fehler bei Simulation: {str(e)}")

def run_scheduler():
    schedule.every().day.at("00:01").do(job_write_history)
    schedule.every().day.at("00:10").do(job_learn)
    schedule.every(6).hours.do(job_simulation)

    print("🔄 Scheduler läuft...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    run_scheduler()
