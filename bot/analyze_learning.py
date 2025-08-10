# analyze_learning.py — Auswertung Lernlog
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple, Optional

PRIMARY_FILE = "learning_log.json"
LEGACY_FILE = "learn_log.json"

def _parse_iso(ts: str) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def _to_bool_or_percent(entry: Dict[str, Any]) -> Tuple[Optional[bool], Optional[float]]:
    """
    Liefert (correct_bool, success_percent).
    Unterstützt Felder:
      - correct: bool
      - success: bool/int/float (0..1 oder 0..100)
    """
    if "correct" in entry:
        try:
            cb = bool(entry["correct"])
            return cb, 100.0 if cb else 0.0
        except Exception:
            pass
    if "success" in entry:
        try:
            s = entry["success"]
            # akzeptiere 0/1, 0..1, 0..100
            if isinstance(s, bool):
                return s, 100.0 if s else 0.0
            val = float(s)
            if 0.0 <= val <= 1.0:
                return val >= 0.5, val * 100.0
            # sonst 0..100
            val = max(0.0, min(100.0, val))
            return val >= 50.0, val
        except Exception:
            pass
    return None, None

def _load_logs() -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    for path in (PRIMARY_FILE, LEGACY_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, list):
                data.extend(obj)
        except Exception as e:
            print(f"[Learning] Warnung: {path} konnte nicht gelesen werden: {e}")
    # nur valide minimal-Felder behalten
    cleaned: List[Dict[str, Any]] = []
    for e in data:
        coin = str(e.get("coin", "")).upper().strip()
        if not coin:
            continue
        ts = e.get("timestamp") or e.get("time") or e.get("date")
        dt = _parse_iso(ts) if ts else None
        corr, succ = _to_bool_or_percent(e)
        if corr is None and succ is None:
            # notfalls ableiten aus "result" == "win"/"loss"
            res = str(e.get("result", "")).lower()
            if res in ("win", "success", "correct", "true"):
                corr, succ = True, 100.0
            elif res in ("loss", "fail", "false", "wrong"):
                corr, succ = False, 0.0
        cleaned.append({
            "coin": coin,
            "timestamp": dt,
            "correct": corr if corr is not None else False,
            "success_pct": succ if succ is not None else (100.0 if corr else 0.0),
            "raw": e,
        })
    # nach Zeit sortieren (älteste zuerst; None ans Ende)
    cleaned.sort(key=lambda x: x["timestamp"] or datetime.min.replace(tzinfo=timezone.utc))
    return cleaned

def _filter_timeframe(rows: List[Dict[str, Any]], days: Optional[int]) -> List[Dict[str, Any]]:
    if not days or days <= 0:
        return rows
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out: List[Dict[str, Any]] = []
    for r in rows:
        dt = r["timestamp"]
        if isinstance(dt, datetime) and dt >= cutoff:
            out.append(r)
    return out

def compute_stats(days: Optional[int] = None) -> Dict[str, Any]:
    rows = _filter_timeframe(_load_logs(), days)
    if not rows:
        return {
            "overall": {"total": 0, "correct": 0, "wrong": 0, "accuracy_pct": 0.0},
            "by_coin": {},
            "latest": [],
        }

    total = len(rows)
    correct = sum(1 for r in rows if r["correct"])
    wrong = total - correct
    overall_acc = round(100.0 * correct / total, 2) if total else 0.0

    by_coin = defaultdict(lambda: {"total": 0, "correct": 0, "wrong": 0})
    for r in rows:
        c = r["coin"]
        by_coin[c]["total"] += 1
        if r["correct"]:
            by_coin[c]["correct"] += 1
        else:
            by_coin[c]["wrong"] += 1

    by_coin_final: Dict[str, Dict[str, Any]] = {}
    for coin, s in by_coin.items():
        acc = round(100.0 * s["correct"] / s["total"], 2) if s["total"] else 0.0
        by_coin_final[coin] = {**s, "accuracy_pct": acc}

    # Letzte 10 Entscheidungen (für Telegram)
    latest = rows[-10:]
    latest_fmt = [
        f"{i+1}. {r['coin']} — {'✅' if r['correct'] else '❌'} "
        f"{(r['timestamp'].isoformat() if r['timestamp'] else 'n/a')}"
        for i, r in enumerate(latest)
    ]

    return {
        "overall": {"total": total, "correct": correct, "wrong": wrong, "accuracy_pct": overall_acc},
        "by_coin": by_coin_final,
        "latest": latest_fmt,
    }

def generate_learning_stats(days: Optional[int] = None) -> List[str]:
    """
    Liefert Telegram-freundliche Zeilen:
    - Kopfzeile Overall
    - Top Coins nach Accuracy
    - Letzte 10 Entscheidungen
    """
    stats = compute_stats(days=days)
    if stats["overall"]["total"] == 0:
        return ["ℹ️ Noch keine Lern-Daten vorhanden."]

    lines: List[str] = []
    o = stats["overall"]
    lines.append(f"🧠 Lernstatistik (letzte {days} Tage)" if days else "🧠 Lernstatistik (gesamt)")
    lines.append(f"Gesamt: {o['total']} — ✅ {o['correct']} / ❌ {o['wrong']} — Accuracy: {o['accuracy_pct']}%")

    # Top 10 Coins
    coins = list(stats["by_coin"].items())
    coins.sort(key=lambda kv: (kv[1]["accuracy_pct"], kv[1]["total"]), reverse=True)
    lines.append("\n🏆 Top Coins (Accuracy):")
    for coin, s in coins[:10]:
        lines.append(f"• {coin}: ✅ {s['correct']} / ❌ {s['wrong']} → {s['accuracy_pct']}% (n={s['total']})")

    # Latest
    if stats["latest"]:
        lines.append("\n📅 Letzte 10 Entscheidungen:")
        lines.extend(stats["latest"])

    return lines

def export_learning_report(path: str = "learning_report.json", days: Optional[int] = None) -> str:
    stats = compute_stats(days=days)
    # Timestamps für Export wieder in ISO umwandeln (latest ist bereits Text)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return path
