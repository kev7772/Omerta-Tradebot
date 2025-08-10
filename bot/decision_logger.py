# decision_logger.py — robust, atomic, backward-compatible
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union, Optional

DECISION_LOG_FILE = "decision_log.json"

DecisionItem = Dict[str, Any]
DecisionsInput = Union[
    Dict[str, Union[str, Dict[str, Any]]],   # {"BTC":"buy", "ETH":{"action":"hold","confidence":0.7}}
    List[DecisionItem],                      # [{"coin":"BTC","action":"buy",...}, ...]
    List[Tuple[str, str]]                    # [("BTC","buy"), ("ETH","sell")]
]

# ---------- intern ----------

def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

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

def _normalize_action(a: Any) -> str:
    if a is None:
        return "hold"
    s = str(a).strip().lower()
    return s if s in ("buy", "sell", "hold") else "hold"

def _normalize_coin(c: Any) -> str:
    return str(c).strip().upper() if c is not None else ""

def _normalize_decisions(decisions: DecisionsInput,
                         *,
                         default_source: Optional[str] = None) -> List[DecisionItem]:
    """
    Akzeptiert dict/list/tuple-Formate und erzeugt eine Liste standardisierter Einträge.
    """
    out: List[DecisionItem] = []
    if decisions is None:
        return out

    if isinstance(decisions, dict):
        for coin, val in decisions.items():
            coin_norm = _normalize_coin(coin)
            if isinstance(val, dict):
                action = _normalize_action(val.get("action"))
                item = {
                    "coin": coin_norm,
                    "action": action,
                    "confidence": val.get("confidence"),
                    "reason": val.get("reason"),
                    "source": val.get("source", default_source),
                }
            else:
                item = {
                    "coin": coin_norm,
                    "action": _normalize_action(val),
                    "source": default_source,
                }
            out.append(item)
        return out

    if isinstance(decisions, list):
        for entry in decisions:
            if isinstance(entry, dict):
                coin = _normalize_coin(entry.get("coin"))
                action = _normalize_action(entry.get("action"))
                item = {
                    "coin": coin,
                    "action": action,
                    "confidence": entry.get("confidence"),
                    "reason": entry.get("reason"),
                    "source": entry.get("source", default_source),
                }
                out.append(item)
            elif isinstance(entry, tuple) and len(entry) == 2:
                coin, action = entry
                out.append({
                    "coin": _normalize_coin(coin),
                    "action": _normalize_action(action),
                    "source": default_source,
                })
    return out

# ---------- öffentlich ----------

def log_trade_decisions(decisions: DecisionsInput,
                        *,
                        source: Optional[str] = None,
                        extra_meta: Optional[Dict[str, Any]] = None) -> int:
    """
    Hängt Entscheidungen an decision_log.json an (atomar).
    - decisions: dict/list/tuples (siehe _normalize_decisions)
    - source: z. B. "strategy_v2" oder "ghost_exit"
    - extra_meta: wird pro Eintrag unter "meta" mitgeschrieben
    Rückgabe: Anzahl geschriebener Einträge.
    """
    normalized = _normalize_decisions(decisions, default_source=source)
    if not normalized:
        print("[DecisionLog] Keine validen Entscheidungen erhalten.")
        return 0

    log = _load_json_list(DECISION_LOG_FILE)

    date_str = _utc_date()
    ts_iso = _utc_iso()

    for item in normalized:
        entry = {
            # Felder für Abwärtskompatibilität:
            "date": date_str,                # wie bisher (YYYY-MM-DD)
            "coin": item.get("coin", ""),
            "action": item.get("action", "hold"),
            # neue, hilfreiche Felder:
            "timestamp": ts_iso,             # ISO-UTC
            "confidence": item.get("confidence"),
            "reason": item.get("reason"),
            "source": item.get("source"),
        }
        if extra_meta:
            entry["meta"] = extra_meta
        log.append(entry)

    _atomic_write_json(DECISION_LOG_FILE, log)
    print(f"📥 Trade-Entscheidungen geloggt ({date_str}): {len(normalized)} Einträge")
    return len(normalized)

# Optional: direkter Helper, falls du „on demand“ aus logic ziehen willst
def log_from_logic(make_trade_decision_fn) -> int:
    """
    Ruft make_trade_decision_fn() auf und versucht, daraus Entscheidungen zu extrahieren.
    Erwartete Rückgaben:
      - dict {coin: action | {action, confidence, reason}}
      - list[dict{coin, action, ...}]
      - list[tuple(coin, action)]
    """
    try:
        decisions = make_trade_decision_fn()
    except Exception as e:
        print(f"[DecisionLog] make_trade_decision() Fehler: {e}")
        return 0
    return log_trade_decisions(decisions, source="logic")
