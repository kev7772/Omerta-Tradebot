import schedule
import time
import os
from trading import get_portfolio, get_profit_estimates
from sentiment_parser import get_sentiment_data
from live_logger import write_history
from feedback_loop import run_feedback_loop
from error_pattern_analyzer import analyze_errors
from telebot import TeleBot

# === Bot-Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = TeleBot(BOT_TOKEN)

# === Autostatus-Funktion ===
def send_autostatus():
    # Portfolio anzeigen
    portfolio = get_portfolio()
    portfolio_msg = "📊 Autostatus — Portfolio:\n"
    for h in portfolio:
        portfolio_msg += f"{h['coin']}: {h['amount']} → {h['value']} €\n"
    bot.send_message(ADMIN_ID, portfolio_msg)

    # Gewinnanalyse
    profits = get_profit_estimates()
    profit_msg = "💰 Buchgewinne:\n"
    for p in profits:
        profit_msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"
    bot.send_message(ADMIN_ID, profit_msg)

    # Sentiment-Analyse
    sentiment = get_sentiment_data()
    sent_msg = f"📡 Marktstimmung: {sentiment['sentiment'].upper()} ({sentiment['score']})\n"
    sent_msg += "📚 Quellen:\n" + "\n".join([f"- {s}" for s in sentiment['sources']])
    bot.send_message(ADMIN_ID, sent_msg)

    # Lernbewertung (Feedback-Modul)
    results = run_feedback_loop()
    if results:
        feedback = "📈 Lernbewertung (Auto):\n"
        for r in results:
            emoji = "✅" if r["success"] > 0 else "❌"
            feedback += f"{emoji} {r['coin']} ({r['date']}) → {r['success']} %\n"
        bot.send_message(ADMIN_ID, feedback)
    else:
        bot.send_message(ADMIN_ID, "📘 Keine offenen Lernbewertungen (Auto).")

    # Fehlermuster-Analyse (neu!)
    fehlerbericht = analyze_errors()
    bot.send_message(ADMIN_ID, fehlerbericht, parse_mode="Markdown")

# === Scheduler dauerhaft starten ===
def run_scheduler():
    print("⏰ Scheduler läuft dauerhaft...")
    schedule.every().day.at("00:05").do(write_history)
    schedule.every().day.at("12:00").do(send_autostatus)

    while True:
        schedule.run_pending()
        time.sleep(30)

from crawler import run_crawler
schedule.every().hour.do(run_crawler)

from crawler_alert import detect_hype_signals

hype_alerts = detect_hype_signals()
if hype_alerts:
    alert_msg = "🚨 Hype-Alarm:\n"
    for h in hype_alerts:
        alert_msg += f"{h['coin']} (Score: {h['score']})\nQuellen: {', '.join(h['sources'])}\n\n"
    bot.send_message(ADMIN_ID, alert_msg)

from ghost_mode import run_ghost_mode

def ghost_schedule():
    entries = run_ghost_mode()
    if entries:
        print(f"[GhostMode] {len(entries)} Ghost Entries erkannt.")
    else:
        print("[GhostMode] Keine Einträge.")

import schedule
from ghost_mode import run_ghost_mode
from live_logger import write_history
from feedback_loop import run_feedback_loop
from simulator import run_simulation

def run_scheduled_tasks():
    schedule.every(1).hours.do(run_ghost_mode)        # Ghost Entries prüfen
    schedule.every(1).hours.do(write_history)         # Prices in history.json schreiben
    schedule.every(6).hours.do(run_feedback_loop)     # Lernlogik regelmäßig bewerten
    schedule.every(12).hours.do(run_simulation)       # Simulation laufen lassen

def run_scheduler():
    run_scheduled_tasks()
    import time
    while True:
        schedule.run_pending()
        time.sleep(1)
schedule.every(1).hours.do(ghost_schedule)

from ghost_mode import run_ghost_mode, check_ghost_exit

def run_scheduled_tasks():
    schedule.every(1).hours.do(run_ghost_mode)
    schedule.every(1).hours.do(check_ghost_exit)  # Exit-Logik aktiv
    ...

def get_scheduler_status():
    from datetime import datetime

    status = "🗓️ *Omerta Scheduler Status:*\n\n"
    status += "🧠 Aktive Hintergrundprozesse:\n"
    status += "• Ghost Entry Check (1h)\n"
    status += "• Ghost Exit Analyse (1h)\n"
    status += "• Live Preis-Logger (1h)\n"
    status += "• Hype/Trend-Analyse (1h)\n"
    status += "• Feedback-Learning (6h)\n"
    status += "• Historische Simulation (12h)\n"
    status += "• Autostatus-Bericht (12:00 täglich)\n"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status += f"\n🕒 Stand: {now}"

    return status
