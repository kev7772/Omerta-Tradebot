# feedback_loop.py — live-only, robust gegen neue history/decision Formate
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

DECISION_LOG_FILE = "decision_log.json"
HISTORY_FILE = "history.json"
LEARNING_LOG_FILE = "learning_log.json"

# Konfiguration
DEFAULT_HORIZON_DAYS = 3
TOLERANCE_HOURS_BASELINE = 24    # wie weit um die Entscheidungszeit dürfen wir den Einstiegspreis suchen
TOLERANCE_HOURS_TARGET = 24      # wie weit um die Zielzeit (decision+horizon) dürfen wir den Zielpreis suchen

def _atomic_write(path: str, data: Any) -> None:
    d = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=d, suffix=".tmp", encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp = tf.name
    os.replace(tmp, path)

def _load_json_list(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def _parse_iso(ts: str | None) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def _parse_date_utc(date_str: str | None) -> Optional[datetime]:
    if not isinstance(date_str, str):
        return None
    try:
        # Altes Format: "YYYY-MM-DD" → als 00:00 UTC interpretieren
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None

def _nearest_price(history_idx: Dict[str, List[Tuple[datetime, float]]],
                   coin: str,
                   target_dt: datetime,
                   tolerance_hours: float) -> Optional[Tuple[datetime, float]]:
    rows = history_idx.get(coin.upper(), [])
    if not rows:
        return None
    tol = timedelta(hours=float(tolerance_hours))
    best: Optional[Tuple[datetime, float]] = None
    best_delta = None
    for ts, price in rows:
        delta = abs(ts - target_dt)
        if delta <= tol:
            if best is None or delta < best_delta:
                best = (ts, price)
                best_delta = delta
    return best

def _build_history_index(history: List[Dict[str, Any]]) -> Dict[str, List[Tuple[datetime, float]]]:
    idx: Dict[str, List[Tuple[datetime, float]]] = {}
    for e in history:
        coin = str(e.get("coin", "")).upper().strip()
        price = e.get("price")
        ts = _parse_iso(e.get("timestamp"))
        if not coin or price is None or not isinstance(price, (int, float)) or ts is None:
            continue
        idx.setdefault(coin, []).append((ts, float(price)))
    # sortieren je Coin
    for c in idx:
        idx[c].sort(key=lambda t: t[0])
    return idx

def _decision_time(entry: Dict[str, Any]) -> Optional[datetime]:
    # Bevorzugt ISO timestamp, sonst date (YYYY-MM-DD)
    t = _parse_iso(entry.get("timestamp"))
    if t:
        return t
    d = _parse_date_utc(entry.get("date"))
    if d:
        return d
    return None

def _normalize_percent(p_old: float, p_new: float) -> float:
    if p_old == 0:
        return 0.0
    return round(((p_new - p_old) / p_old) * 100.0, 2)

def run_feedback_loop(*,
                      horizon_days: int = DEFAULT_HORIZON_DAYS,
                      tolerance_baseline_hours: float = TOLERANCE_HOURS_BASELINE,
                      tolerance_target_hours: float = TOLERANCE_HOURS_TARGET) -> List[Dict[str, Any]]:
    """
    Evaluates open decisions using real prices from history.json (live_logger format).
    - horizon_days: X Tage nach der Entscheidung
    - tolerance_*_hours: wie weit um die relevanten Zeitpunkte wir Preise akzeptieren
    Rückgabe: Liste der ausgewerteten Einträge (coin, date/timestamp, success %).
    """
    decisions = _load_json_list(DECISION_LOG_FILE)
    history = _load_json_list(HISTORY_FILE)
    learning_log = _load_json_list(LEARNING_LOG_FILE)

    if not decisions or not history:
        return []

    # History-Index je Coin → [(ts, price), ...]
    hidx = _build_history_index(history)
    now_utc = datetime.now(timezone.utc)

    evaluated: List[Dict[str, Any]] = []
    updated_any = False

    for d in decisions:
        # Bereits ausgewertet? Dann überspringen
        status = (d.get("status") or "").lower()
        if status in ("evaluated", "closed", "done"):
            continue

        coin = str(d.get("coin", "")).upper().strip()
        if not coin:
            continue

        dec_dt = _decision_time(d)
        if dec_dt is None:
            # Keine verwertbare Zeitangabe → skip
            continue

        # Zielzeitpunkt
        target_dt = dec_dt + timedelta(days=int(horizon_days))
        if target_dt > now_utc:
            # Noch nicht fällig
            continue

        # Einstiegspreis: vorhandene Felder nutzen, sonst aus History (nächster Preis um dec_dt)
        base_price = d.get("price") or d.get("baseline_price")
        if not isinstance(base_price, (int, float)):
            nearest_base = _nearest_price(hidx, coin, dec_dt, tolerance_baseline_hours)
            if not nearest_base:
                # Kein Basispunkt gefunden → nicht bewertbar
                continue
            _, base_price = nearest_base

        # Zielpreis: nächster Preis um target_dt
        nearest_target = _nearest_price(hidx, coin, target_dt, tolerance_target_hours)
        if not nearest_target:
            # Zielpreis nicht auffindbar → später nochmal
            continue
        target_ts, target_price = nearest_target

        success = _normalize_percent(float(base_price), float(target_price))

        # Decision erweitern/markieren
        d["baseline_price"] = float(base_price)
        d["evaluated_price"] = float(target_price)
        d["evaluated_at"] = target_ts.replace(microsecond=0).isoformat()
        d["success"] = success
        d["status"] = "evaluated"
        updated_any = True

        # Learning-Log ergänzen (kompakt, für analyze_learning)
        learning_log.append({
            "timestamp": target_ts.replace(microsecond=0).isoformat(),
            "coin": coin,
            "decision": d.get("action") or d.get("decision"),
            "success": success,
            "horizon_days": horizon_days,
            "origin": "feedback_loop"
        })

        evaluated.append({
            "coin": coin,
            "decision_time": dec_dt.replace(microsecond=0).isoformat(),
            "evaluated_at": target_ts.replace(microsecond=0).isoformat(),
            "success": success
        })

    if updated_any:
        _atomic_write(DECISION_LOG_FILE, decisions)
        _atomic_write(LEARNING_LOG_FILE, learning_log)

    return evaluated
