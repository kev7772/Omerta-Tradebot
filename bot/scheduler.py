# scheduler.py — stable, keeps your original timings

import schedule
import time
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telebot import TeleBot

# === Bot Setup (failsafe) ===
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
try:
    ADMIN_ID = int(ADMIN_ID)
except Exception:
    ADMIN_ID = None  # kein Telegram-Versand möglich, Jobs laufen trotzdem

bot = TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# === Imports für geplante Tasks ===
from trading import get_portfolio, get_profit_estimates
from sentiment_parser import get_sentiment_data
from live_logger import write_history
from feedback_loop import run_feedback_loop
from error_pattern_analyzer import analyze_errors
from simulator import run_simulation
from crawler import run_crawler, get_crawler_data
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
    try:
        if not os.path.exists(file):
            with open(file, "w", encoding="utf-8") as f:
                json.dump([], f)
    except Exception as e:
        print(f"[Init] Konnte {file} nicht anlegen: {e}")

# === Autostatus (täglicher Bericht) ===
def send_autostatus():
    try:
        # Portfolio
        portfolio = get_portfolio() or []
        portfolio_msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            portfolio_msg += f"{h.get('coin')}: {h.get('amount')} → {h.get('value')} €\n"
        _send(portfolio_msg)

        # Gewinne
        profits = get_profit_estimates() or []
        profit_msg = "💰 Buchgewinne:\n"
        for p in profits:
            profit_msg += f"{p.get('coin')}: {p.get('profit')} € ({p.get('percent')}%)\n"
        _send(profit_msg)

        # Marktstimmung
        sentiment = get_sentiment_data() or {}
        sent_label = str(sentiment.get('sentiment', '')).upper()
        sent_score = sentiment.get('score', 0)
        sources = sentiment.get('sources', [])
        sent_msg = f"📡 Marktstimmung: {sent_label} ({sent_score})\n"
        if sources:
            sent_msg += "📚 Quellen:\n" + "\n".join([f"- {s}" for s in sources])
        _send(sent_msg)

        # Lernbewertung
        results = run_feedback_loop() or []
        if results:
            feedback = "📈 Lernbewertung (Auto):\n"
            for r in results:
                success = r.get("success", 0)
                emoji = "✅" if success > 0 else "❌"
                feedback += f"{emoji} {r.get('coin')} ({r.get('date')}) → {success} %\n"
            _send(feedback)
        else:
            _send("📘 Keine offenen Lernbewertungen (Auto).")

        # Fehleranalyse
        fehlerbericht = analyze_errors()
        _send(fehlerbericht, parse_mode="Markdown")

    except Exception as e:
        _send(f"⚠️ Fehler bei /autostatus: {e}")

# === Ghost Mode Wrapper ===
def ghost_entry_job():
    entries = _job("GhostMode Entry", run_ghost_mode)
    if entries:
        lines = [f"🕵🏽‍♂️ Ghost Entries: {len(entries)}"]
        for e in entries[:10]:
            lines.append(
                f"• {e.get('coin')} — sc:{e.get('sentiment_score')} "
                f"m:{e.get('mentions')} t:{e.get('trend_score')}"
            )
        _send("\n".join(lines))

def ghost_exit_job():
    exits = _job("GhostMode Exit", check_ghost_exit)
    if exits:
        lines = [f"🏁 Ghost Exits: {len(exits)}"]
        for e in exits[:10]:
            lines.append(
                f"• {e.get('coin')} — success:{e.get('success')} "
                f"reason:{e.get('exit_reason')}"
            )
        _send("\n".join(lines))

# === Logger / Simulation / Hype ===
def log_prices_task():
    _job("Logger", write_history)

def simulation_task():
    _job("Simulation", run_simulation)

def hype_check():
    def _run():
        alerts = detect_hype_signals() or []
        if alerts:
            alert_msg = "🚨 Hype-Alarm:\n"
            for h in alerts:
                alert_msg += f"{h.get('coin')} (Score: {h.get('score')})\n"
                src = h.get('sources') or []
                if src:
                    alert_msg += "Quellen: " + ", ".join(src) + "\n"
                alert_msg += "\n"
            _send(alert_msg)
    _job("HypeCheck", _run)

# === Crawler-Job (Fix für NameError) ===
def crawler_job():
    _job("Crawler", run_crawler)
    # Kurz-Update senden (optional)
    try:
        data = get_crawler_data() or {}
        coins = data.get("coins", [])
        if coins:
            top = sorted(coins, key=lambda x: x.get("mentions", 0), reverse=True)[:3]
            msg = "📡 Crawler Update — Top Trends:\n"
            for c in top:
                msg += f"• {c.get('coin')} — Mentions: {c.get('mentions')} | Trend: {c.get('trend_score')}\n"
            _send(msg)
    except Exception as e:
        print(f"[Crawler] Update-Fehler: {e}")

# === Autostatus 12:00 Europa/Berlin (DST-sicher) ===
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
    print(f"[Scheduler] Autostatus 12:00 Berlin -> {utc_time_str} UTC (next: {job.next_run})")

# === Zeitplan (deine Original-Intervalle) ===
def run_scheduled_tasks():
    schedule.every(1).hours.do(ghost_entry_job)
    schedule.every(1).hours.do(ghost_exit_job)
    schedule.every(1).hours.do(log_prices_task)
    schedule.every(1).hours.do(crawler_job)        # <— jetzt definiert
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
    try:
        ghost_entry_job()
        ghost_exit_job()
        log_prices_task()
        crawler_job()
        hype_check()
        run_feedback_loop()
        simulation_task()
        send_autostatus()
    except Exception as e:
        print(f"[Scheduler] Fehler bei Initialläufen: {e}")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[Scheduler] run_pending Fehler: {e}")
            _send(f"⚠️ Scheduler-Fehler: {e}")
        time.sleep(30)

# === Statusabruf ===
def get_scheduler_status():
    try:
        now_local = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S %Z")
        status = "🗓️ *Omerta Scheduler Status:*\n\n"
        for job in schedule.get_jobs():
            tags = ",".join(job.tags) if getattr(job, "tags", None) else "-"
            status += f"• {job} — next: {job.next_run} — tags: {tags}\n"
        status += f"\n🕒 Stand (Berlin): {now_local}"
        return status
    except Exception as e:
        return f"⚠️ Konnte Status nicht ermitteln: {e}"
