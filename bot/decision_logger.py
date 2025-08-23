# decision_logger.py — loggt ALLE Einträge, dedupe & merge
# Stand: 2025-08-23 (Fix: 'decision' wird mitgeschrieben)

from __future__ import annotations
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Union, Optional

DECISION_LOG_FILE = "decision_log.json"

DecisionItem = Dict[str, Any]
DecisionsInput = Union[
    Dict[str, Union[str, Dict[str, Any]]],
    List[DecisionItem],
    List[Tuple[str, str]]
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

def _normalize_action(a: Any, fallback: str = "hold") -> str:
    if a is None:
        return fallback
    s = str(a).strip().lower()
    return s if s in ("buy", "sell", "hold") else fallback

def _normalize_coin(c: Any) -> str:
    return str(c).strip().upper() if c is not None else ""

def _to_float_or_none(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _normalize_decisions(decisions: DecisionsInput,
                         *,
                         default_source: Optional[str] = None) -> List[DecisionItem]:
    out: List[DecisionItem] = []
    if decisions is None:
        return out

    def _mk_item(coin: Any, payload: Dict[str, Any]) -> DecisionItem:
        coin_norm = _normalize_coin(coin)
        action = _normalize_action(payload.get("action") or payload.get("signal") or "hold")
        return {
            "coin": coin_norm,
            "action": action,
            "signal": payload.get("signal"),
            "percent": _to_float_or_none(payload.get("percent")),
            "price": _to_float_or_none(payload.get("price")),
            "confidence": _to_float_or_none(payload.get("confidence")),
            "reason": payload.get("reason"),
            "source": payload.get("source", default_source),
            **{k: v for k, v in payload.items()
               if k not in {"action", "signal", "percent", "price", "confidence", "reason", "source", "coin"}}
        }

    if isinstance(decisions, dict):
        for coin, val in decisions.items():
            if isinstance(val, dict):
                out.append(_mk_item(coin, val))
            else:
                out.append(_mk_item(coin, {"action": val}))
        return out

    if isinstance(decisions, list):
        for entry in decisions:
            if isinstance(entry, dict):
                out.append(_mk_item(entry.get("coin"), entry))
            elif isinstance(entry, tuple) and len(entry) == 2:
                coin, action = entry
                out.append(_mk_item(coin, {"action": action}))
    return out

def _merge_entry(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(old)
    for k in ("action", "decision", "signal", "percent", "price", "confidence", "reason", "source"):
        v = new.get(k)
        if v is not None and v != "":
            merged[k] = v
    for k, v in new.items():
        if k not in merged or merged.get(k) in (None, "", []):
            merged[k] = v
    return merged

# ---------- öffentlich ----------

def log_trade_decisions(decisions: DecisionsInput,
                        *,
                        source: Optional[str] = None,
                        extra_meta: Optional[Dict[str, Any]] = None,
                        dedupe: bool = True,
                        dedupe_key: str = "coin_date_source") -> int:
    normalized = _normalize_decisions(decisions, default_source=source)
    if not normalized:
        print("[DecisionLog] Keine validen Entscheidungen erhalten.")
        return 0

    log = _load_json_list(DECISION_LOG_FILE)

    date_str = _utc_date()
    ts_iso = _utc_iso()

    index = {}
    if dedupe:
        for i, e in enumerate(log):
            if dedupe_key == "coin_date_source":
                key = (e.get("coin"), e.get("date"), e.get("source"))
            else:
                key = (e.get("coin"), e.get("date"))
            index[key] = i

    changed = 0

    for item in normalized:
        coin = item.get("coin", "")
        if not coin:
            continue

        action = item.get("action", "hold")

        entry_base = {
            "date": date_str,            # YYYY-MM-DD
            "coin": coin,
            "action": action,
            "decision": action,          # <<< WICHTIG: Alias fürs Learning
            "timestamp": ts_iso,         # ISO-UTC
            "signal": item.get("signal"),
            "percent": item.get("percent"),
            "price": item.get("price"),
            "confidence": item.get("confidence"),
            "reason": item.get("reason"),
            "source": item.get("source", source),
        }
        if extra_meta:
            entry_base["meta"] = extra_meta

        for k, v in item.items():
            if k not in entry_base:
                entry_base[k] = v

        if dedupe:
            if dedupe_key == "coin_date_source":
                k = (entry_base["coin"], entry_base["date"], entry_base.get("source"))
            else:
                k = (entry_base["coin"], entry_base["date"])
            if k in index:
                pos = index[k]
                log[pos] = _merge_entry(log[pos], entry_base)
                changed += 1
                continue
            else:
                index[k] = len(log)

        log.append(entry_base)
        changed += 1

    _atomic_write_json(DECISION_LOG_FILE, log)
    print(f"📥 Trade-Entscheidungen geloggt ({date_str}): {changed} Einträge")
    return changed

def log_from_logic(make_trade_decision_fn) -> int:
    try:
        decisions = make_trade_decision_fn()
    except Exception as e:
        print(f"[DecisionLog] make_trade_decision() Fehler: {e}")
        return 0
    return log_trade_decisions(decisions, source="logic")
