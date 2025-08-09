import schedule
import time
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telebot import TeleBot

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
try:
    ADMIN_ID = int(ADMIN_ID)
except Exception:
    ADMIN_ID = None

bot = TeleBot(BOT_TOKEN) if BOT_TOKEN else None

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

# === Helper ===
def _send(msg, **kwargs):
    if bot and ADMIN_ID:
        try:
            bot.send_message(ADMIN_ID, msg, **kwargs)
        except Exception as e:
            print(f"[Telegram] Sendefehler: {e}")

def _job(name, fn):
    try:
        return fn()
    except Exception as e:
        print(f"[{name}] Fehler: {type(e).__name__}: {e}")
        _send(f"⚠️ {name} Fehler: {e}")
        return None

# === Sicherstellen, dass JSON-Dateien existieren ===
for file in ["crawler_data.json", "learning_log.json", "history.json"]:
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump([], f)

# === Autostatus ===
def send_autostatus():
    try:
        portfolio = get_portfolio() or []
        portfolio_msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            portfolio_msg += f"{h['coin']}: {h['amount']} → {h['value']} €\n"
        _send(portfolio_msg)

        profits = get_profit_estimates() or []
        profit_msg = "💰 Buchgewinne:\n"
        for p in profits:
            profit_msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"
        _send(profit_msg)

        sentiment = get_sentiment_data() or {}
        sent_label = str(sentiment.get('sentiment', '')).upper()
        sent_score = sentiment.get('score', 0)
        sources = sentiment.get('sources', [])
        sent_msg = f"📡 Marktstimmung: {sent_label} ({sent_score})\n"
        if sources:
            sent_msg += "📚 Quellen:\n" + "\n".join([f"- {s}" for s in sources])
        _send(sent_msg)

        results = run_feedback_loop() or []
        if results:
            feedback = "📈 Lernbewertung (Auto):\n"
            for r in results:
                emoji = "✅" if r["success"] > 0 else "❌"
                feedback += f"{emoji} {r['coin']} ({r['date']}) → {r['success']} %\n"
            _send(feedback)
        else:
            _send("📘 Keine offenen Lernbewertungen (Auto).")

        fehlerbericht = analyze_errors()
        _send(fehlerbericht, parse_mode="Markdown")

    except Exception as e:
        _send(f"⚠️ Fehler bei /autostatus: {e}")

# === Ghost Mode ===
def ghost_entry_job():
    entries = _job("GhostMode Entry", run_ghost_mode)
    if entries:
        _send(f"🕵🏽‍♂️ {len(entries)} Ghost Entries erkannt.")

def ghost_exit_job():
    exits = _job("GhostMode Exit", check_ghost_exit)
    if exits:
        _send(f"🏁 {len(exits)} Ghost Exits erkannt.")

# === Logger ===
def log_prices_task():
    _job("Logger", write_history)

# === Simulation ===
def simulation_task():
    _job("Simulation", run_simulation)

# === Hype Check ===
def hype_check():
    def _run():
        alerts = detect_hype_signals() or []
        if alerts:
            alert_msg = "🚨 Hype-Alarm:\n"
            for h in alerts:
                alert_msg += f"{h['coin']} (Score: {h['score']})\n"
                if 'sources' in h:
                    alert_msg += "Quellen: " + ", ".join(h['sources']) + "\n\n"
            _send(alert_msg)
    _job("HypeCheck", _run)

# === Autostatus um 12:00 Berlin (DST-sicher) ===
def schedule_autostatus_local(hour=12, minute=0):
    try:
        schedule.clear('autostatus')
    except Exception:
        pass
    utc = ZoneInfo("UTC")
    berlin = ZoneInfo("Europe/Berlin")
    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_berlin = now_utc.astimezone(berlin)
    target_berlin = now_berlin.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_berlin >= target_berlin:
        target_berlin += timedelta(days=1)
    target_utc = target_berlin.astimezone(utc)
    utc_time_str = target_utc.strftime("%H:%M")
    job = schedule.every().day.at(utc_time_str).do(send_autostatus)
    job.tag('autostatus')
    print(f"[Scheduler] Autostatus 12:00 Berlin -> {utc_time_str} UTC")

# === Zeitplan (aus Ursprungsdatei) ===
def run_scheduled_tasks():
    schedule.every(1).hours.do(run_ghost_mode)
    schedule.every(1).hours.do(check_ghost_exit)
    schedule.every(1).hours.do(log_prices_task)
    schedule.every(1).hours.do(run_crawler)
    schedule.every(1).hours.do(hype_check)
    schedule.every(6).hours.do(run_feedback_loop)
    schedule.every(1).hours.do(simulation_task)
    schedule_autostatus_local(12, 0)

# === Scheduler starten + Sofortläufe ===
def run_scheduler():
    print("⏰ Omerta Scheduler läuft...")
    run_scheduled_tasks()

    # Sofortige Erstläufe
    print("[Scheduler] Initiale Sofortläufe gestartet...")
    ghost_entry_job()
    ghost_exit_job()
    log_prices_task()
    run_crawler()
    hype_check()
    run_feedback_loop()
    simulation_task()
    send_autostatus()

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[Scheduler] Fehler: {e}")
            _send(f"⚠️ Scheduler-Fehler: {e}")
        time.sleep(30)

# === Statusabruf ===
def get_scheduler_status():
    now_local = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S %Z")
    status = "🗓️ *Omerta Scheduler Status:*\n\n"
    for job in schedule.get_jobs():
        tags = ",".join(job.tags) if job.tags else "-"
        status += f"• {job} — next: {job.next_run} — tags: {tags}\n"
    status += f"\n🕒 Stand (Berlin): {now_local}"
    return status
