# auto_learn.py — robustes Auto-Learn
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LEARNING_LOG = "learning_log.json"

# Schwellen (kannst du bei Bedarf anpassen)
BUY_OK_THRESHOLD   = 5.0   # %   -> buy gilt als korrekt, wenn actual_percent >= +5%
SELL_OK_THRESHOLD  = -5.0  # %   -> sell gilt als korrekt, wenn actual_percent <= -5%
HOLD_BAND          = 5.0   # %   -> hold gilt als korrekt, wenn -5% .. +5%

def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _atomic_write_json(path: str, data: Any) -> None:
    d = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, dir=d, suffix=".tmp", encoding="utf-8") as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp = tf.name
    os.replace(tmp, path)

def _load_json_list(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def _normalize_percent(p: float | int) -> float:
    """
    Akzeptiert 0.1 (=10%), 10 (=10%) oder 10.0.
    Gibt immer Prozent in [−1000, +1000] zurück (geclamped).
    """
    try:
        val = float(p)
    except Exception:
        return 0.0
    # wenn zwischen -1 und 1, behandeln wir es als Anteil (0.1 = 10 %)
    if -1.0 <= val <= 1.0:
        val *= 100.0
    # clamp gegen Ausreißer
    if val > 1000: val = 1000.0
    if val < -1000: val = -1000.0
    return val

def _judge(decision: str, actual_pct: float) -> bool:
    d = (decision or "").strip().lower()
    if d == "buy":
        return actual_pct >= BUY_OK_THRESHOLD
    if d == "sell":
        return actual_pct <= SELL_OK_THRESHOLD
    if d == "hold":
        return (-HOLD_BAND) <= actual_pct <= HOLD_BAND
    # unbekannte Entscheidung -> als falsch werten
    return False

def learn_from_decision(coin: str,
                        decision: str,
                        actual_percent: float | int,
                        *,
                        horizon_days: Optional[int] = None,
                        meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Vergleicht die Entscheidung mit dem echten Verlauf.
    decision: 'buy' | 'hold' | 'sell'
    actual_percent: tatsächliche Entwicklung nach X Tagen; akzeptiert 0.1 (=10%) oder 10 (=10%).
    horizon_days: optional, z. B. 7, 14, 30 – wird mitgeloggt.
    meta: optionales Dict für zusätzliche Felder (z. B. Quelle, Signal-ID usw.)
    Rückgabe: Ergebnis-Dict (inkl. normalisiertem Prozent & korrekt-Flag).
    """
    pct = _normalize_percent(actual_percent)
    correct = _judge(decision, pct)

    result: Dict[str, Any] = {
        "coin": (coin or "").upper(),
        "decision": (decision or "").lower(),
        "actual_percent": pct,
        "correct": bool(correct),
        "horizon_days": horizon_days,
        "timestamp": _utc_iso(),
    }
    if isinstance(meta, dict) and meta:
        result["meta"] = meta

    data = _load_json_list(LEARNING_LOG)
    data.append(result)
    _atomic_write_json(LEARNING_LOG, data)
    return result

# Optional: Bulk-Helper, falls du mehrere Entscheidungen in einem Rutsch bewerten willst
def learn_bulk(items: List[Dict[str, Any]],
               *,
               default_horizon_days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    items: Liste von Dicts, jedes mit mindestens coin, decision, actual_percent
    Beispiel-Item:
      {"coin": "BTC", "decision": "buy", "actual_percent": 0.08, "horizon_days": 7, "meta": {...}}
    """
    results: List[Dict[str, Any]] = []
    for it in items:
        res = learn_from_decision(
            it.get("coin", ""),
            it.get("decision", ""),
            it.get("actual_percent", 0),
            horizon_days=it.get("horizon_days", default_horizon_days),
            meta=it.get("meta"),
        )
        results.append(res)
    return results
