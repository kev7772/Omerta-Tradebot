import schedule
import time
import os
from telebot import TeleBot
from datetime import datetime
from learn_scheduler import evaluate_pending_learnings

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = TeleBot(BOT_TOKEN)

# === Imports für geplante Tasks ===
from trading import get_portfolio, get_profit_estimates
from sentiment_parser import get_sentiment_data
from live_logger import write_history
from feedback_loop import run_feedback_loop
from error_pattern_analyzer import analyze_errors
from simulator import run_simulation
from crawler import run_crawler
from crawler_alert import detect_hype_signals
from ghost_mode import run_ghost_mode, check_ghost_exit
from learn_scheduler import evaluate_pending_learnings  # ✅ Auto-Learn integriert

# === Autostatus (täglich) ===
def send_autostatus():
    try:
        portfolio = get_portfolio()
        profits = get_profit_estimates()
        sentiment = get_sentiment_data()

        portfolio_msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            portfolio_msg += f"{h['coin']}: {h['amount']} → {h['value']} €\n"

        portfolio_msg += "\n💰 Gewinne:\n"
        for p in profits:
            portfolio_msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"

        portfolio_msg += f"\n📡 Sentiment: {sentiment['sentiment'].upper()} ({sentiment['score']})"

        bot.send_message(ADMIN_ID, portfolio_msg)
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Fehler bei Autostatus: {e}")

# === Geplante Tasks ===
def run_scheduler():
    # 1× pro Stunde → Preise & History loggen
    schedule.every(1).hours.do(write_history)

    # 1× pro Tag → Autostatus an Telegram senden
    schedule.every().day.at("08:00").do(send_autostatus)

    # 1× pro Tag → Feedback-Learning
    schedule.every().day.at("09:00").do(run_feedback_loop)

    # 1× pro Tag → Fehleranalyse
    schedule.every().day.at("10:00").do(analyze_errors)

    # 1× pro Tag → Crawler starten
    schedule.every().day.at("11:00").do(run_crawler)

    # 1× pro Tag → Hype-Signale prüfen
    schedule.every().day.at("11:05").do(detect_hype_signals)

    # 1× pro Tag → Ghost-Mode prüfen
    schedule.every().day.at("12:00").do(run_ghost_mode)

    # 1× pro Tag → Ghost-Exits checken
    schedule.every().day.at("12:05").do(check_ghost_exit)

    # 1× pro Tag → Simulationen laufen lassen
    schedule.every().day.at("13:00").do(run_simulation)

    # ✅ NEU: 1× pro Tag → Ausstehende Lernbewertungen prüfen
    schedule.every().day.at("14:00").do(evaluate_pending_learnings)

    schedule.every(1).hours.do(learn_job)

    print("✅ Scheduler gestartet und alle Tasks geladen.")

    while True:
        schedule.run_pending()
        time.sleep(1)

# Lernzahlen (optional)
try:
    open_cnt = 0
    learned_cnt = 0
    if os.path.exists("decision_log.json"):
        with open("decision_log.json", "r", encoding="utf-8") as f:
            open_cnt = len(json.load(f))
    if os.path.exists("learning_log.json"):
        with open("learning_log.json", "r", encoding="utf-8") as f:
            learned_cnt = len(json.load(f))
    _send(f"🧠 Auto-Learning: {learned_cnt} gelernt | {open_cnt} offen")
except Exception:
    pass

def learn_job():
    """Bewertet ausstehende Entscheidungen und meldet, wie viele verarbeitet wurden."""
    # Vorher zählen
    before = 0
    try:
        if os.path.exists("decision_log.json"):
            with open("decision_log.json", "r", encoding="utf-8") as f:
                before = len(json.load(f))
    except Exception:
        pass

    _job("AutoLearn", evaluate_pending_learnings)

    # Nachher zählen
    after = 0
    try:
        if os.path.exists("decision_log.json"):
            with open("decision_log.json", "r", encoding="utf-8") as f:
                after = len(json.load(f))
    except Exception:
        pass

    processed = max(0, before - after)
    if processed > 0:
        _send(f"🧠 Auto-Learn: {processed} Entscheidung(en) bewertet.")
