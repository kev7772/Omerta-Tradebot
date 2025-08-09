# scheduler.py — clean, stable, DST-safe (Europe/Berlin)

import schedule
import time
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telebot import TeleBot

# === Bot Setup (defensiv) ===
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
try:
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else None
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
from learn_scheduler import evaluate_pending_learnings  # Auto-Learn integriert

# ---------- Helper ----------
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

def _schedule_daily_berlin(hour: int, minute: int, fn, tag: str | None = None):
    """
    Plant einen Job für eine Berlin-Uhrzeit (DST-sicher), indem die Zeit in UTC
    umgerechnet und mit schedule.every().day.at(UTC) registriert wird.
    """
    utc = ZoneInfo("UTC")
    berlin = ZoneInfo("Europe/Berlin")

    now_utc = datetime.utcnow().replace(tzinfo=utc)
    now_berlin = now_utc.astimezone(berlin)

    target_berlin = now_berlin.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_berlin >= target_berlin:
        target_berlin += timedelta(days=1)

    target_utc = target_berlin.astimezone(utc)
    utc_time_str = target_utc.strftime("%H:%M")

    job = schedule.every().day.at(utc_time_str).do(fn)
    if tag:
        job.tag(tag)

    print(f"[Scheduler] {fn.__name__} {hour:02d}:{minute:02d} Berlin -> {utc_time_str} UTC (next: {job.next_run})")
    return job

# ---------- Jobs ----------
def send_autostatus():
    try:
        portfolio = get_portfolio() or []
        profits = get_profit_estimates() or []
        sentiment = get_sentiment_data() or {}

        msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            msg += f"{h.get('coin')}: {h.get('amount')} → {h.get('value')} €\n"

        msg += "\n💰 Gewinne:\n"
        for p in profits:
            msg += f"{p.get('coin')}: {p.get('profit')} € ({p.get('percent')}%)\n"

        msg += f"\n📡 Sentiment: {str(sentiment.get('sentiment','')).upper()} ({sentiment.get('score',0)})"

        # Lernzahlen
        try:
            open_cnt = 0
            learned_cnt = 0
            if os.path.exists("decision_log.json"):
                with open("decision_log.json", "r", encoding="utf-8") as f:
                    open_cnt = len(json.load(f))
            if os.path.exists("learning_log.json"):
                with open("learning_log.json", "r", encoding="utf-8") as f:
                    learned_cnt = len(json.load(f))
            msg += f"\n🧠 Auto-Learning: {learned_cnt} gelernt | {open_cnt} offen"
        except Exception:
            pass

        _send(msg)
    except Exception as e:
        _send(f"❌ Fehler bei Autostatus: {e}")

def learn_job():
    before = 0
    try:
        if os.path.exists("decision_log.json"):
            with open("decision_log.json", "r", encoding="utf-8") as f:
                before = len(json.load(f))
    except Exception:
        pass

    _job("AutoLearn", evaluate_pending_learnings)

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

# ---------- Zeitplan ----------
def run_scheduler():
    print("⏰ Omerta Scheduler läuft...")

    # Stündlich
    schedule.every(1).hours.do(lambda: _job("Logger", write_history))
    schedule.every(1).hours.do(learn_job)

    # Täglich zu Berlin-Zeiten (DST-sicher)
    _schedule_daily_berlin(8, 0,  send_autostatus,       tag="autostatus")
    _schedule_daily_berlin(9, 0,  lambda: _job("FeedbackLoop", run_feedback_loop))
    _schedule_daily_berlin(10, 0, lambda: _job("ErrorAnalysis", analyze_errors))
    _schedule_daily_berlin(11, 0, lambda: _job("Crawler", run_crawler))
    _schedule_daily_berlin(11, 5, lambda: _job("HypeCheck", detect_hype_signals))
    _schedule_daily_berlin(12, 0, lambda: _job("GhostMode Entry", run_ghost_mode))
    _schedule_daily_berlin(12, 5, lambda: _job("GhostMode Exit", check_ghost_exit))
    _schedule_daily_berlin(13, 0, lambda: _job("Simulation", run_simulation))

    print("✅ Scheduler gestartet und alle Tasks geladen.")

    # Sofortläufe beim Start (optional)
    try:
        learn_job()
        send_autostatus()
        _job("Crawler (Initial)", run_crawler)
    except Exception as e:
        print(f"[Scheduler] Fehler bei Initialläufen: {e}")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[Scheduler] run_pending Fehler: {e}")
            _send(f"⚠️ Scheduler-Fehler: {e}")
        time.sleep(1)

# ---------- Status für /schedulerstatus ----------
def get_scheduler_status():
    try:
        berlin = ZoneInfo("Europe/Berlin")
        now_local = datetime.now(berlin).strftime("%Y-%m-%d %H:%M:%S %Z")
        lines = ["🗓️ *Omerta Scheduler Status:*\n"]
        for job in schedule.get_jobs():
            lines.append(f"• {job} — next: {job.next_run}")
        lines.append(f"\n🕒 Stand (Berlin): {now_local}")
        return "\n".join(lines)
    except Exception as e:
        return f"⚠️ Konnte Status nicht ermitteln: {e}"
