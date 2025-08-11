# error_pattern_analyzer.py — robuste Fehlermuster-Analyse für Simulationen
# Stand: 2025-08-11

from __future__ import annotations
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Unterstütze mehrere potenzielle Dateinamen
LOGFILES = ("log_simulation.json", "simulation_log.json")

# ---- Helpers ----
def _parse_iso(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def _norm_decision(val: Any) -> str:
    s = str(val or "").strip().lower()
    mapping = {
        "gekauft": "buy", "kauf": "buy",
        "verkauft": "sell", "verkauf": "sell",
        "gehalten": "hold", "halte": "hold",
    }
    return mapping.get(s, s if s in ("buy", "sell", "hold") else "")

def _norm_success(x: Any) -> float:
    """Normalisiert Erfolg/Performance auf Prozentbasis."""
    try:
        if isinstance(x, bool):
            return 100.0 if x else -100.0
        v = float(x)
    except Exception:
        return 0.0
    if -1.0 <= v <= 1.0:
        v *= 100.0
    return max(min(v, 1000.0), -1000.0)

def _load_json(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

def _load_logs() -> List[Dict[str, Any]]:
    """Lädt Logs aus allen bekannten Dateinamen und merged sie."""
    rows: List[Dict[str, Any]] = []
    seen = set()
    for p in LOGFILES:
        for e in _load_json(p):
            # Duplikate grob vermeiden (coin+timestamp)
            key = (str(e.get("coin")).upper(), str(e.get("timestamp") or e.get("date")))
            if key not in seen:
                rows.append(e)
                seen.add(key)
    return rows

# ---- Kernanalyse ----
def analyze_errors_struct(
    *,
    logfile: Optional[str] = None,
    window_days: Optional[int] = None,
    min_errors_threshold: int = 2,
    min_attempts_per_coin: int = 1,
    fail_success_cutoff_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Strukturierte Analyse der Fehlmuster.
    Gibt IMMER die Keys: ok, found, offenders, coins, params zurück.
    """
    rows = _load_json(logfile) if logfile else _load_logs()

    params = {
        "window_days": window_days,
        "min_errors_threshold": min_errors_threshold,
        "min_attempts_per_coin": min_attempts_per_coin,
        "fail_success_cutoff_pct": fail_success_cutoff_pct,
        "source": logfile or ",".join(LOGFILES),
    }

    if not rows:
        return {
            "ok": True,
            "found": False,
            "offenders": [],
            "coins": {},
            "summary": "Keine Simulationsdaten.",
            "params": params,
        }

    # Zeitraumfilter (optional)
    if window_days and window_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        tmp = []
        for e in rows:
            ts = e.get("timestamp") or e.get("date")
            dt = _parse_iso(ts) if isinstance(ts, str) else None
            if dt is None or dt >= cutoff:
                tmp.append(e)
        rows = tmp

    stats = defaultdict(lambda: {
        "count": 0, "fails": 0,
        "by_action": {"buy": {"c":0,"f":0}, "sell":{"c":0,"f":0}, "hold":{"c":0,"f":0}}
    })

    for e in rows:
        coin = str(e.get("coin", "???")).upper()
        decision = _norm_decision(e.get("entscheidung") or e.get("decision"))
        success_raw = e.get("success", e.get("pnl", e.get("performance", e.get("return"))))
        success_pct = _norm_success(success_raw)

        s = stats[coin]
        s["count"] += 1
        if decision in ("buy", "sell", "hold"):
            s["by_action"][decision]["c"] += 1

        if success_pct < float(fail_success_cutoff_pct):
            s["fails"] += 1
            if decision in ("buy", "sell", "hold"):
                s["by_action"][decision]["f"] += 1

    coins_out: Dict[str, Any] = {}
    offenders: List[Tuple[str, float, int, int]] = []

    for coin, s in stats.items():
        total = s["count"]
        fails = s["fails"]
        if total < min_attempts_per_coin:
            continue
        fail_rate = round(100.0 * fails / total, 1) if total else 0.0

        by_act = {}
        for act, vv in s["by_action"].items():
            c, f = vv["c"], vv["f"]
            by_act[act] = {
                "attempts": c,
                "fails": f,
                "fail_rate_pct": round(100.0 * f / c, 1) if c else 0.0
            }

        coins_out[coin] = {
            "attempts": total,
            "fails": fails,
            "fail_rate_pct": fail_rate,
            "by_action": by_act,
        }
        if fails >= min_errors_threshold:
            offenders.append((coin, fail_rate, fails, total))

    offenders.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

    return {
        "ok": True,
        "found": bool(offenders),
        "offenders": offenders,       # Liste von (coin, fail_rate_pct, fails, total)
        "coins": coins_out,
        "params": params,
    }

# ---- String-Ausgabe (für Telegram/Scheduler) ----
def analyze_errors(
    *,
    logfile: Optional[str] = None,
    window_days: Optional[int] = None,
    min_errors_threshold: int = 2,
    min_attempts_per_coin: int = 1,
    fail_success_cutoff_pct: float = 0.0,
) -> str:
    """Erzeugt kompakte Textausgabe (Markdown-tauglich)."""
    res = analyze_errors_struct(
        logfile=logfile,
        window_days=window_days,
        min_errors_threshold=min_errors_threshold,
        min_attempts_per_coin=min_attempts_per_coin,
        fail_success_cutoff_pct=fail_success_cutoff_pct,
    )

    if not res.get("ok"):
        return "⚠️ Analyse fehlgeschlagen."

    coins = res.get("coins", {})
    offenders = res.get("offenders", [])
    params = res.get("params", {})

    if not coins:
        return "⚠️ Noch keine Simulationsdaten vorhanden."

    header = "🧠 *Fehlermuster-Analyse*"
    sub = []
    if params.get("window_days"):
        sub.append(f"(letzte {params['window_days']} Tage)")
    if params.get("fail_success_cutoff_pct", 0.0) != 0.0:
        sub.append(f"(Cutoff {params['fail_success_cutoff_pct']}%)")
    if sub:
        header += " " + " ".join(sub)

    out = [header, ""]

    if offenders:
        out.append("🔻 *Auffällig (Fehlerquote absteigend):*")
        for coin, rate, fails, total in offenders[:10]:
            out.append(f"• {coin}: {fails}/{total} Fehler ({rate}%)")
    else:
        out.append("✅ Keine auffälligen Fehlmuster erkannt.")

    # Breakdown (Top 5 nach Versuchen)
    top = sorted(coins.items(), key=lambda kv: kv[1].get("attempts", 0), reverse=True)[:5]
    if top:
        out.append("\n📊 *Breakdown (Top 5 nach Versuchen):*")
        for coin, s in top:
            ba = s.get("by_action", {})
            out.append(
                f"• {coin}: buy {ba.get('buy',{}).get('fails',0)}/{ba.get('buy',{}).get('attempts',0)} | "
                f"sell {ba.get('sell',{}).get('fails',0)}/{ba.get('sell',{}).get('attempts',0)} | "
                f"hold {ba.get('hold',{}).get('fails',0)}/{ba.get('hold',{}).get('attempts',0)}"
            )

    return "\n".join(out)
