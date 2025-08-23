# learn_scheduler.py
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from autolearn import learn_from_decision
from history_tools import get_change_since

# --- Zeitzone Berlin ---
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Berlin")
except Exception:
    TZ = None

DECISION_LOG = "decision_log.json"
LEARNING_LOG = "learning_log.json"
EVAL_DELAY_DAYS = 1          # nach X Tagen bewerten
MAX_RETRY = 7                # max. erneute Versuche, wenn Daten fehlen

# ---------------------------
# Helpers: Zeit + JSON I/O
# ---------------------------

def now_dt() -> datetime:
    return datetime.now(TZ) if TZ else datetime.now()

def _iso(dt: datetime) -> str:
    return dt.isoformat()

def _parse_ts(ts_str: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts_str, fmt)
            if dt.tzinfo is None and TZ:
                dt = dt.replace(tzinfo=TZ)
            return dt
        except Exception:
            continue
    dt = datetime.fromisoformat(ts_str)
    if dt.tzinfo is None and TZ:
        dt = dt.replace(tzinfo=TZ)
    return dt

def _read_json_safely(path: str, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json_safely(path: str, data) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

# ---------------------------
# Logging fürs Lernen
# ---------------------------

def log_learning_result(coin: str, decision: str, change: float) -> None:
    logs = _read_json_safely(LEARNING_LOG, default=[])
    if not isinstance(logs, list):
        logs = []
    logs.append({
        "date": _iso(now_dt()),
        "coin": str(coin).upper(),
        "decision": decision,
        "change": round(float(change), 2)
    })
    _write_json_safely(LEARNING_LOG, logs)

# ---------------------------
# Kernlogik
# ---------------------------

def _eligible_for_eval(entry: Dict[str, Any], cutoff_days: int) -> bool:
    if entry.get("evaluated_at"):
        return False
    ts = entry.get("timestamp")
    if not ts:
        return False
    try:
        created = _parse_ts(ts)
    except Exception:
        return False
    age = now_dt() - created
    return age >= timedelta(days=cutoff_days)

def _increment_retry(entry: Dict[str, Any]) -> None:
    entry["retry_count"] = int(entry.get("retry_count", 0)) + 1

def _mark_evaluated(entry: Dict[str, Any]) -> None:
    entry["evaluated_at"] = _iso(now_dt())

def evaluate_pending_learnings(evaluation_delay_days: int = EVAL_DELAY_DAYS, max_retry: int = MAX_RETRY) -> None:
    logs = _read_json_safely(DECISION_LOG, default=[])
    if not isinstance(logs, list):
        print("❌ Fehler: decision_log.json ist beschädigt oder kein Listentyp.")
        return

    if not logs:
        print("ℹ️ Keine Einträge in decision_log.json.")
        return

    updated: List[Dict[str, Any]] = []
    learned_count = 0
    still_open = 0

    for entry in logs:
        coin = str(entry.get("coin", "")).upper()
        decision = entry.get("decision") or entry.get("action") or ""   # <<< Fix
        ts_str = entry.get("timestamp")

        if entry.get("evaluated_at"):
            updated.append(entry)
            continue

        if not _eligible_for_eval(entry, evaluation_delay_days):
            updated.append(entry)
            continue

        try:
            created_dt = _parse_ts(ts_str)
            since_date = created_dt.strftime("%Y-%m-%d")
            change = get_change_since(coin, since_date)

            if change is not None:
                learn_from_decision(coin, decision, change)
                log_learning_result(coin, decision, change)
                _mark_evaluated(entry)
                updated.append(entry)
                learned_count += 1
                print(f"📘 Gelernt: {coin} → {decision} → {round(change, 2)}%")
            else:
                _increment_retry(entry)
                if entry["retry_count"] <= max_retry:
                    updated.append(entry)
                    still_open += 1
                    print(f"⚠️ Keine Kursdaten für {coin} seit {since_date}. Retry {entry['retry_count']}/{max_retry}.")
                else:
                    entry["eval_note"] = "max_retry_reached_no_data"
                    _mark_evaluated(entry)
                    updated.append(entry)
                    print(f"⛔ Max. Retries erreicht für {coin} ({since_date}). Markiere als abgeschlossen.")

        except Exception as e:
            _increment_retry(entry)
            updated.append(entry)
            still_open += 1
            print(f"⚠️ Fehler bei Bewertung von {coin}: {e}. Retry {entry['retry_count']}/{max_retry}.")

    _write_json_safely(DECISION_LOG, updated)
    print(f"✅ Lernbewertung: {learned_count} gelernt, {still_open} offen.")

if __name__ == "__main__":
    evaluate_pending_learnings()
