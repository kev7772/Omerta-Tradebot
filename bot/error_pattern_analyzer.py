# error_pattern_analyzer.py — robuste Fehlermuster-Analyse für Simulationen
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

LOGFILE = "simulation_log.json"

# ---- Normalizer ----
def _parse_iso(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def _norm_decision(val: Any) -> str:
    s = str(val or "").strip().lower()
    # deutsch → englisch mappen
    mapping = {
        "gekauft": "buy",
        "kauf": "buy",
        "verkauft": "sell",
        "verkauf": "sell",
        "gehalten": "hold",
        "halte": "hold",
    }
    return mapping.get(s, s if s in ("buy", "sell", "hold") else "")

def _norm_success(x: Any) -> float:
    """
    Normalisiert Erfolg/Performance auf Prozent-Basis:
    - bool True/False → 100 / 0
    - -1..1 → *100 (Anteil)
    - sonst direkt als Prozent interpretiert, auf [-1000, 1000] begrenzt
    """
    try:
        if isinstance(x, bool):
            return 100.0 if x else -100.0  # bool als klarer Win/Loss
        v = float(x)
    except Exception:
        return 0.0
    if -1.0 <= v <= 1.0:
        v *= 100.0
    # clamp
    if v > 1000: v = 1000.0
    if v < -1000: v = -1000.0
    return v

def _load_json(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []

# ---- Kernanalyse ----
def analyze_errors_struct(
    logfile: str = LOGFILE,
    *,
    window_days: Optional[int] = None,
    min_errors_threshold: int = 2,
    min_attempts_per_coin: int = 1,
    fail_success_cutoff_pct: float = 0.0,
) -> Dict[str, Any]:
    """
    Liefert strukturierte Analyse:
      - window_days: optionaler Zeitraum (z. B. 30 → letzte 30 Tage)
      - min_errors_threshold: ab wie vielen Fehlern Coin als auffällig gilt
      - min_attempts_per_coin: erst ab n Versuchen bewerten
      - fail_success_cutoff_pct: <0 => Fehler, z. B. 0.0 (negativ), -5.0 (unter -5%)
    """
    rows = _load_json(logfile)
    if not rows:
        return {"ok": True, "found": False, "summary": "Keine Simulationsdaten.", "coins": {}}

    # ggf. Zeitraum filtern
    if window_days and window_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        tmp = []
        for e in rows:
            ts = e.get("timestamp") or e.get("date")  # akzeptiere beides
            dt = _parse_iso(ts) if isinstance(ts, str) else None
            if dt is None:
                # wenn kein Datum vorhanden, nicht filtern
                tmp.append(e)
            elif dt >= cutoff:
                tmp.append(e)
        rows = tmp

    stats = defaultdict(lambda: {"count": 0, "fails": 0, "by_action": {"buy": {"c":0,"f":0}, "sell":{"c":0,"f":0}, "hold":{"c":0,"f":0}}})

    for e in rows:
        coin = str(e.get("coin", "???")).upper()
        decision = _norm_decision(e.get("entscheidung") or e.get("decision"))
        success_raw = e.get("success")
        # manche Logs nutzen andere Felder wie "pnl" oder "result"
        if success_raw is None:
            success_raw = e.get("pnl") or e.get("performance") or e.get("return")

        success_pct = _norm_success(success_raw)

        stats[coin]["count"] += 1
        if decision in ("buy", "sell", "hold"):
            stats[coin]["by_action"][decision]["c"] += 1

        # Fehlerregel: success_pct < cutoff → Fehler
        is_fail = success_pct < float(fail_success_cutoff_pct)
        if is_fail:
            stats[coin]["fails"] += 1
            if decision in ("buy", "sell", "hold"):
                stats[coin]["by_action"][decision]["f"] += 1

    # Ergebnis aufbereiten
    coins_out: Dict[str, Any] = {}
    offenders = []
    for coin, s in stats.items():
        total = s["count"]
        fails = s["fails"]
        if total < min_attempts_per_coin:
            continue
        fail_rate = round(100.0 * fails / total, 1) if total else 0.0

        by_act = {}
        for act, vv in s["by_action"].items():
            c = vv["c"]
            f = vv["f"]
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
        "offenders": offenders,  # Liste von (coin, fail_rate_pct, fails, total)
        "coins": coins_out,
        "params": {
            "window_days": window_days,
            "min_errors_threshold": min_errors_threshold,
            "min_attempts_per_coin": min_attempts_per_coin,
            "fail_success_cutoff_pct": fail_success_cutoff_pct,
        }
    }

# ---- String-Ausgabe (für Telegram/Scheduler) ----
def analyze_errors(
    logfile: str = LOGFILE,
    *,
    window_days: Optional[int] = None,
    min_errors_threshold: int = 2,
    min_attempts_per_coin: int = 1,
    fail_success_cutoff_pct: float = 0.0,
) -> str:
    """
    Erzeugt eine kompakte Textausgabe (Markdown-tauglich).
    """
    res = analyze_errors_struct(
        logfile=logfile,
        window_days=window_days,
        min_errors_threshold=min_errors_threshold,
        min_attempts_per_coin=min_attempts_per_coin,
        fail_success_cutoff_pct=fail_success_cutoff_pct,
    )

    if not res.get("ok"):
        return "⚠️ Analyse fehlgeschlagen."

    coins = res["coins"]
    offenders = res["offenders"]
    params = res["params"]

    if not coins:
        return "⚠️ Noch keine Simulationsdaten vorhanden."

    header = "🧠 *Fehlermuster-Analyse*"
    sub = []
    if params["window_days"]:
        sub.append(f"(letzte {params['window_days']} Tage)")
    if params["fail_success_cutoff_pct"] != 0.0:
        sub.append(f"(Cutoff {params['fail_success_cutoff_pct']}%)")
    if sub:
        header += " " + " ".join(sub)

    out = [header, ""]

    # Auffällige Coins
    if offenders:
        out.append("🔻 *Auffällig (Fehlerquote absteigend):*")
        for coin, rate, fails, total in offenders[:10]:
            out.append(f"• {coin}: {fails}/{total} Fehler ({rate}%)")
    else:
        out.append("✅ Keine auffälligen Fehlmuster erkannt.")

    # Optional: kleine Action-Breakdown für die Top 5 Coins nach Versuchen
    top = sorted(coins.items(), key=lambda kv: kv[1]["attempts"], reverse=True)[:5]
    if top:
        out.append("\n📊 *Breakdown (Top 5 nach Versuchen):*")
        for coin, s in top:
            ba = s["by_action"]
            out.append(
                f"• {coin}: buy {ba['buy']['fails']}/{ba['buy']['attempts']} | "
                f"sell {ba['sell']['fails']}/{ba['sell']['attempts']} | "
                f"hold {ba['hold']['fails']}/{ba['hold']['attempts']}"
            )

    return "\n".join(out)
