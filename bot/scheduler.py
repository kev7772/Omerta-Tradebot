import schedule
import time
import os
import json
from telebot import TeleBot
from datetime import datetime, timedelta

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

# === Sicherstellen, dass JSON-Dateien existieren ===
for file in ["crawler_data.json", "learning_log.json", "history.json"]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

# === Autostatus (täglicher Bericht) ===
def send_autostatus():
    try:
        # Portfolio
        portfolio = get_portfolio()
        portfolio_msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            portfolio_msg += f"{h['coin']}: {h['amount']} → {h['value']} €\n"
        bot.send_message(ADMIN_ID, portfolio_msg)

        # Gewinne
        profits = get_profit_estimates()
        profit_msg = "💰 Buchgewinne:\n"
        for p in profits:
            profit_msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"
        bot.send_message(ADMIN_ID, profit_msg)

        # Marktstimmung
        sentiment = get_sentiment_data()
        sent_msg = f"📡 Marktstimmung: {sentiment['sentiment'].upper()} ({sentiment['score']})\n"
        sent_msg += "📚 Quellen:\n" + "\n".join([f"- {s}" for s in sentiment['sources']])
        bot.send_message(ADMIN_ID, sent_msg)

        # Lernbewertung
        results = run_feedback_loop()
        if results:
            feedback = "📈 Lernbewertung (Auto):\n"
            for r in results:
                emoji = "✅" if r["success"] > 0 else "❌"
                feedback += f"{emoji} {r['coin']} ({r['date']}) → {r['success']} %\n"
            bot.send_message(ADMIN_ID, feedback)
        else:
            bot.send_message(ADMIN_ID, "📘 Keine offenen Lernbewertungen (Auto).")

        # Fehleranalyse
        fehlerbericht = analyze_errors()
        bot.send_message(ADMIN_ID, fehlerbericht, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ Fehler bei /autostatus: {e}")

# === Ghost Mode Zeitsteuerung ===
def ghost_schedule():
    entries = run_ghost_mode()
    print(f"[GhostMode] {len(entries)} Ghost Entries erkannt." if entries else "[GhostMode] Keine Einträge erkannt.")

# === Preislogger mit Logging ===
def log_prices_task():
    try:
        write_history()
        print(f"[Logger] Preise gespeichert um {datetime.now()}")
    except Exception as e:
        print(f"[Logger] Fehler beim Speichern der Preise: {e}")

# === Simulation mit Logging ===
def simulation_task():
    try:
        run_simulation()
        print(f"[Simulation] Historische Simulation abgeschlossen um {datetime.now()}")
    except Exception as e:
        print(f"[Simulation] Fehler bei der Simulation: {e}")

# === Hype Check ===
def hype_check():
    try:
        hype_alerts = detect_hype_signals()
        if hype_alerts:
            alert_msg = "🚨 Hype-Alarm:\n"
            for h in hype_alerts:
                alert_msg += f"{h['coin']} (Score: {h['score']})\nQuellen: {', '.join(h['sources'])}\n\n"
            bot.send_message(ADMIN_ID, alert_msg)
    except Exception as e:
        print(f"[HypeCheck] Fehler: {e}")

# === Zeitbasierte Aufgaben definieren ===
def run_scheduled_tasks():
    schedule.every(1).hours.do(run_ghost_mode)
    schedule.every(1).hours.do(check_ghost_exit)
    schedule.every(1).hours.do(log_prices_task)
    schedule.every(1).hours.do(run_crawler)
    schedule.every(1).hours.do(hype_check)
    schedule.every(6).hours.do(run_feedback_loop)
    schedule.every(1).hours.do(simulation_task)  # statt 12h → jede Stunde für permanenten Lernmodus
    schedule.every().day.at("12:00").do(send_autostatus)

# === Scheduler dauerhaft starten ===
def run_scheduler():
    print("⏰ Omerta Scheduler läuft...")
    run_scheduled_tasks()
    while True:
        schedule.run_pending()
        time.sleep(30)

# === Schedulerstatus für Telegram-Befehl ===
def get_scheduler_status():
    now = (datetime.utcnow() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    status = "🗓️ *Omerta Scheduler Status:*\n\n"
    status += "🧠 Aktive Hintergrundprozesse:\n"
    status += "• Ghost Entry Check (1h)\n"
    status += "• Ghost Exit Analyse (1h)\n"
    status += "• Live Preis-Logger (1h)\n"
    status += "• Markt-Crawler (1h)\n"
    status += "• Hype/Trend-Analyse (1h)\n"
    status += "• Feedback-Learning (6h)\n"
    status += "• Historische Simulation (1h)\n"
    status += "• Autostatus-Bericht (12:00 täglich)\n"
    status += f"\n🕒 Stand: {now}"
    return status
