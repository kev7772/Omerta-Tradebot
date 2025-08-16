# scheduler.py — clean, DST-safe (Europe/Berlin) + Auto-Datenfeeds für alle JSON-Logs
from __future__ import annotations

import schedule
import time
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from telebot import TeleBot

# ==== Bot Setup (defensiv) ====
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
try:
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW else None
except Exception:
    ADMIN_ID = None

bot = TeleBot(BOT_TOKEN) if BOT_TOKEN else None

# ==== Projekt-Imports ====
from trading import get_portfolio, get_profit_estimates
from sentiment_parser import get_sentiment_data
from live_logger import write_history, load_history_safe
from feedback_loop import run_feedback_loop
from error_pattern_analyzer import analyze_errors
from simulator import run_simulation, run_live_simulation
from crawler import run_crawler
from crawler_alert import detect_hype_signals
from ghost_mode import run_ghost_mode, check_ghost_exit
from learn_scheduler import evaluate_pending_learnings
from bootstrap_learning import ensure_min_learning_entries

# NEU: Entscheidungen automatisch erzeugen & loggen
from logic import make_trade_decision
from decision_logger import log_trade_decisions

# KI-Training (ECHT)
from train_ki_model import train_model

# Optional für Binance-Snapshots
try:
    from binance.client import Client
except Exception:
    Client = None


# ---------------- Format-Helper (wie in main.py) ----------------
def _to_float(x) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def fmt_eur(x) -> str:
    return f"{_to_float(x):.2f} €"

def fmt_pct(x) -> str:
    return f"{_to_float(x):.2f}%"

def fmt_amt(x, max_decimals: int = 8) -> str:
    s = f"{_to_float(x):.{max_decimals}f}"
    s = s.rstrip("0").rstrip(".")
    return s if s else "0"


# ---------------- Helper ----------------
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


# ---------------- Live-Logger ----------------
def log_snapshot_from_binance(symbols=("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT")) -> int:
    """
    Holt Preise direkt von Binance und schreibt sie in history.json.
    """
    if Client is None:
        print("[Logger] Binance-Client nicht verfügbar.")
        return 0
    try:
        api = os.getenv("BINANCE_API_KEY")
        sec = os.getenv("BINANCE_API_SECRET")
        if not api or not sec:
            print("[Logger] BINANCE_API_KEY/SECRET fehlen — überspringe Binance-Snapshot.")
            return 0
        client = Client(api, sec)
        prices_input = []
        for sym in symbols:
            try:
                t = client.get_symbol_ticker(symbol=sym)
                coin = sym.replace("USDT", "")
                price = float(t["price"])
                prices_input.append({"coin": coin, "price": price})
            except Exception as e:
                print(f"[Logger] Symbol {sym} Fehler: {e}")
        if not prices_input:
            return 0
        n = write_history(prices_input)
        return n
    except Exception as e:
        print(f"[Logger] Binance Snapshot Fehler: {e}")
        return 0


def log_snapshot_from_estimates() -> int:
    """
    Baut prices_input aus get_profit_estimates(), loggt nur Einträge mit echtem 'price'/'current'.
    """
    try:
        estimates = get_profit_estimates() or []
        prices_input = []
        for e in estimates:
            coin = e.get("coin")
            price = e.get("current", e.get("price"))
            try:
                price = float(price)
            except Exception:
                price = None
            if coin and isinstance(price, (int, float)):
                prices_input.append({"coin": str(coin), "price": float(price)})
        if not prices_input:
            print("[Logger] Keine validen Preise in get_profit_estimates() gefunden.")
            return 0
        return write_history(prices_input)
    except Exception as e:
        print(f"[Logger] Estimates Snapshot Fehler: {e}")
        return 0


# ---------------- Pruning (alle Logs) ----------------
def _prune_json_list(file_path: str, max_entries: int) -> None:
    try:
        if not os.path.exists(file_path):
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return
        if len(data) <= max_entries:
            return
        cut = data[-max_entries:]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cut, f, ensure_ascii=False, indent=2)
        print(f"[Prune] {os.path.basename(file_path)} -> {len(cut)} Einträge")
    except Exception as e:
        print(f"[Prune] Fehler bei {file_path}: {e}")


def prune_history(max_days: int = 120, backup_path: str = "history_backup.json") -> None:
    """
    Pruned history.json im Format { 'YYYY-MM-DD': {...}, ... } auf die letzten `max_days`.
    Legt ein Backup der letzten max_days Tage ab.
    """
    try:
        if not os.path.exists("history.json"):
            return
        with open("history.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data:
            return

        # Keys sind Tages-Strings; nach Datum sortieren und trimmen
        keys_sorted = sorted(data.keys())
        if len(keys_sorted) <= max_days:
            return

        keep_keys = keys_sorted[-max_days:]
        pruned = {k: data[k] for k in keep_keys}

        # Backup (nur die behaltenen Tage)
        try:
            with open(backup_path, "w", encoding="utf-8") as bf:
                json.dump(pruned, bf, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Logger] Backup-Fehler: {e}")

        with open("history.json", "w", encoding="utf-8") as f:
            json.dump(pruned, f, ensure_ascii=False, indent=2)

        print(f"[Logger] History auf {len(keep_keys)} Tage gekürzt (max={max_days}).")
    except Exception as e:
        print(f"[Logger] Prune-Fehler: {e}")


def prune_other_logs():
    # leichte Caps für die restlichen Logs
    _prune_json_list("learning_log.json",   10_000)
    _prune_json_list("decision_log.json",    5_000)
    _prune_json_list("simulation_log.json",  5_000)
    _prune_json_list("ghost_log.json",       5_000)


# ---------------- Business Jobs (Auto-Feeds) ----------------
def send_autostatus():
    try:
        portfolio = get_portfolio() or []
        profits = get_profit_estimates() or []
        sentiment = get_sentiment_data() or {}

        msg = "📊 Autostatus — Portfolio:\n"
        for h in portfolio:
            coin = h.get('coin')
            amount = fmt_amt(h.get('amount', 0))
            value = fmt_eur(h.get('value', 0))
            msg += f"{coin}: {amount} → {value}\n"

        msg += "\n💰 Gewinne:\n"
        if profits:
            for p in profits:
                coin = p.get('coin')
                profit = fmt_eur(p.get('profit', 0))
                percent = fmt_pct(p.get('percent', 0))
                msg += f"{coin}: {profit} ({percent})\n"
        else:
            msg += "—\n"

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


def decisions_cycle():
    """
    Erzeugt Entscheidungen, loggt sie und stößt direkt den Feedback-Loop an.
    -> füllt decision_log.json und (zeitversetzt) learning_log.json
    """
    try:
        decisions = make_trade_decision() or {}
        log_trade_decisions(decisions)
    except Exception as e:
        print(f"[Decisions] Log-Fehler: {e}")
    try:
        run_feedback_loop()
    except Exception as e:
        print(f"[Feedback] Fehler: {e}")


def live_sim_cycle():
    """Füttert simulation_log.json regelmäßig mit Live-Simulationen."""
    try:
        res = run_live_simulation()
        print(f"[LiveSim] {res}")
    except Exception as e:
        print(f"[LiveSim] Fehler: {e}")


def ghost_cycle():
    """Regelmäßiger Ghost-Scan (Entries & Exits) -> ghost_log.json."""
    try:
        run_ghost_mode()
    except Exception as e:
        print(f"[Ghost] Entry-Fehler: {e}")
    try:
        check_ghost_exit()
    except Exception as e:
        print(f"[Ghost] Exit-Fehler: {e}")


def crawler_cycle():
    """Regelmäßiger Crawler + Hype-Check -> crawler_data.json."""
    try:
        run_crawler()
    except Exception as e:
        print(f"[Crawler] Fehler: {e}")
    try:
        detect_hype_signals()
    except Exception as e:
        print(f"[HypeCheck] Fehler: {e}")


# ---------------- KI-Training ----------------
def train_ki_daily():
    res = train_model()
    try:
        if bot and ADMIN_ID:
            msg = (
                "🤖 KI-Training abgeschlossen:\n"
                f"• Samples: {res.get('n_samples')}\n"
                f"• Accuracy: {res.get('accuracy')}\n"
                f"• AUC: {res.get('auc') if res.get('auc') is not None else 'n/a'}\n"
                f"• Stand: {res.get('trained_at')}"
            )
            if res.get("note"):
                msg += f"\n• Hinweis: {res['note']}"
            bot.send_message(ADMIN_ID, msg)
    except Exception:
        pass


# ---------------- Zeitplan ----------------
def run_scheduler():
    print("⏰ Omerta Scheduler läuft...")

    # Live-Logger
    schedule.every(1).hours.do(lambda: _job("Logger (Binance)", log_snapshot_from_binance))
    schedule.every(3).hours.do(lambda: _job("Logger (Estimates)", log_snapshot_from_estimates))
    _schedule_daily_berlin(3, 15, lambda: _job("Logger (Prune+Backup)", prune_history), tag="logger_maintenance")

    # Automatische Datenfeeds
    schedule.every(1).hours.do(decisions_cycle)     # decision_log + feedback
    schedule.every(2).hours.do(live_sim_cycle)      # simulation_log
    schedule.every(3).hours.do(ghost_cycle)         # ghost_log
    schedule.every(6).hours.do(crawler_cycle)       # crawler_data

    # Lernen & Checks
    schedule.every(1).hours.do(learn_job)
    schedule.every(12).hours.do(prune_other_logs)

    # Lernlog-Nachfüllen falls mager
    schedule.every(6).hours.do(lambda: _job("Learning-Nachfuellen",
                                            lambda: ensure_min_learning_entries(min_entries=100, max_cycles=6)))

    # Täglich zu Berlin-Zeiten (DST-sicher)
    _schedule_daily_berlin(8, 0,  send_autostatus,       tag="autostatus")
    _schedule_daily_berlin(9, 0,  lambda: _job("FeedbackLoop (Daily)", run_feedback_loop))
    _schedule_daily_berlin(10, 0, lambda: _job("ErrorAnalysis", analyze_errors))
    _schedule_daily_berlin(13, 0, lambda: _job("Simulation (Historical)", run_simulation))
    _schedule_daily_berlin(3, 15, train_ki_daily, tag="ki_training")  # echtes KI-Training täglich 03:15

    print("✅ Scheduler gestartet und alle Tasks geladen.")

    # Sofortläufe beim Start (sanft)
    try:
        decisions_cycle()
        live_sim_cycle()
        ghost_cycle()
        crawler_cycle()
        send_autostatus()
        _job("Logger (Init Binance)", log_snapshot_from_binance)
    except Exception as e:
        print(f"[Scheduler] Fehler bei Initialläufen: {e}")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[Scheduler] run_pending Fehler: {e}")
            _send(f"⚠️ Scheduler-Fehler: {e}")
        time.sleep(1)


# ---------------- Status für /schedulerstatus ----------------
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
