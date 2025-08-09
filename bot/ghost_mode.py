# ghost_mode.py
# Robust & defensive version – ready to paste

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Tuple

from sentiment_parser import get_sentiment_data
from trading import get_profit_estimates
from crawler import get_crawler_data

GHOST_LOG_PATH = "ghost_log.json"


# ---------------------------
# Helpers: JSON I/O (safe)
# ---------------------------

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


# --------------------------------------
# Normalisierung: Eingangs-Datenquellen
# --------------------------------------

def _normalize_profits(raw: Any) -> List[Dict[str, Any]]:
    """
    Ziel: Liste von Dicts [{coin: 'BTC', percent: 1.23}, ...]
    Akzeptiert u.a.:
      - Liste von Dicts
      - Liste von Strings (nur Coin) -> percent=0
      - Dict {coin: percent}
      - None/sonstiges -> []
    """
    out: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                coin = str(item.get("coin") or item.get("symbol") or item.get("asset") or "").upper()
                if not coin:
                    continue
                percent = float(item.get("percent", item.get("change", 0)) or 0)
                out.append({"coin": coin, "percent": percent})
            else:
                # String / Sonstiges -> nur Coinname
                coin = str(item).upper()
                if coin:
                    out.append({"coin": coin, "percent": 0.0})
    elif isinstance(raw, dict):
        for k, v in raw.items():
            coin = str(k).upper()
            try:
                percent = float(v)
            except Exception:
                percent = 0.0
            out.append({"coin": coin, "percent": percent})
    return out


def _normalize_sentiment(raw: Any) -> Dict[str, Dict[str, float]]:
    """
    Ziel: Dict { 'BTC': {'score': 0.73}, ... }
    Akzeptiert:
      - Dict coin -> score/objekt
      - Liste von Dicts mit 'coin' + 'score'
      - None/sonstiges -> {}
    """
    out: Dict[str, Dict[str, float]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                score = float(v.get("score", 0) or 0)
            else:
                # evtl. direkt eine Zahl
                try:
                    score = float(v)
                except Exception:
                    score = 0.0
            out[str(k).upper()] = {"score": score}
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            coin = str(item.get("coin") or item.get("symbol") or "").upper()
            if not coin:
                continue
            score = float(item.get("score", 0) or 0)
            out[coin] = {"score": score}
    return out


def _normalize_crawler(raw: Any) -> Dict[str, Dict[str, float]]:
    """
    Ziel: Dict { 'BTC': {'mentions': int, 'trend_score': float}, ... }
    Akzeptiert:
      - Liste von Dicts mit 'coin', 'mentions', 'trend_score'
      - Dict coin -> {...}
      - None/sonstiges -> {}
    """
    out: Dict[str, Dict[str, float]] = {}
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                # Liste enthält Strings? -> ignorieren
                continue
            coin = str(item.get("coin") or item.get("symbol") or "").upper()
            if not coin:
                continue
            mentions = int(item.get("mentions", 0) or 0)
            trend = float(item.get("trend_score", item.get("trend", 0)) or 0)
            out[coin] = {"mentions": mentions, "trend_score": trend}
    elif isinstance(raw, dict):
        for k, v in raw.items():
            coin = str(k).upper()
            if isinstance(v, dict):
                mentions = int(v.get("mentions", 0) or 0)
                trend = float(v.get("trend_score", v.get("trend", 0)) or 0)
            else:
                mentions, trend = 0, 0.0
            out[coin] = {"mentions": mentions, "trend_score": trend}
    return out


# --------------------------------------
# Core: Detection / Exit / Analytics
# --------------------------------------

def detect_stealth_entry(profit_data, sentiment_data, crawler_data) -> List[Dict[str, Any]]:
    """
    Bedingungen:
      - percent < 2
      - mentions < 50
      - sentiment.score > 0.6
      - trend_score > 0.4
    """
    profits = _normalize_profits(profit_data)
    senti = _normalize_sentiment(sentiment_data)
    crawl = _normalize_crawler(crawler_data)

    entries: List[Dict[str, Any]] = []
    now_iso = datetime.now().isoformat()

    for p in profits:
        coin = p.get("coin")
        if not coin:
            continue
        percent = float(p.get("percent", 0) or 0)

        s = senti.get(coin, {})
        c = crawl.get(coin, {})
        score = float(s.get("score", 0) or 0)
        mentions = int(c.get("mentions", 0) or 0)
        trend_score = float(c.get("trend_score", 0) or 0)

        if (
            percent < 2
            and mentions < 50
            and score > 0.6
            and trend_score > 0.4
        ):
            entries.append({
                "coin": coin,
                "percent": percent,
                "sentiment_score": round(score, 4),
                "mentions": mentions,
                "trend_score": round(trend_score, 4),
                "reason": "Ghost Entry: Ruhiger Markt, frühes Sentiment, kein Social-Hype",
                "time": now_iso
            })
    return entries


def run_ghost_mode() -> List[Dict[str, Any]]:
    profits = get_profit_estimates()
    sentiment = get_sentiment_data()
    crawler_data = get_crawler_data()

    new_entries = detect_stealth_entry(profits, sentiment, crawler_data)
    if not new_entries:
        return []

    log = _read_json_safely(GHOST_LOG_PATH, default=[])
    if not isinstance(log, list):
        log = []

    log.extend(new_entries)
    _write_json_safely(GHOST_LOG_PATH, log)
    return new_entries


def _should_exit_now(coin: str) -> Tuple[bool, Dict[str, float]]:
    """
    Einfache, deterministische Exit-Heuristik auf Basis aktueller Daten:
      - sentiment_score >= 0.75  ODER
      - mentions >= 200          ODER
      - trend_score >= 0.70
    Liefert (True/False, aktuelle Metriken)
    """
    sentiment = _normalize_sentiment(get_sentiment_data())
    crawler = _normalize_crawler(get_crawler_data())

    s = sentiment.get(coin.upper(), {})
    c = crawler.get(coin.upper(), {})

    score = float(s.get("score", 0) or 0)
    mentions = int(c.get("mentions", 0) or 0)
    trend = float(c.get("trend_score", 0) or 0)

    trigger = (score >= 0.75) or (mentions >= 200) or (trend >= 0.70)
    return trigger, {"sentiment_score": score, "mentions": mentions, "trend_score": trend}


def _estimate_success(coin: str) -> float:
    """
    Erfolgsschätzer 0..1 auf Basis aktueller Stimmung/Trend.
    (Kein Zufall, stabil reproduzierbar.)
    """
    sentiment = _normalize_sentiment(get_sentiment_data())
    crawler = _normalize_crawler(get_crawler_data())

    s = float(sentiment.get(coin.upper(), {}).get("score", 0) or 0)
    t = float(crawler.get(coin.upper(), {}).get("trend_score", 0) or 0)

    # einfache Mischung, gekappt auf [0,1]
    val = 0.5 * s + 0.5 * t
    return max(0.0, min(1.0, round(val, 4)))


def check_ghost_exit() -> List[Dict[str, Any]]:
    entries = _read_json_safely(GHOST_LOG_PATH, default=[])
    if not entries:
        return []

    updated: List[Dict[str, Any]] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("exit_time"):
            # schon abgeschlossen
            continue

        coin = str(entry.get("coin", "")).upper()
        if not coin:
            continue

        trigger, metrics = _should_exit_now(coin)
        if trigger:
            entry["exit_time"] = now
            entry["exit_reason"] = "Hype/Exit-Trigger erreicht"
            entry["exit_metrics"] = {
                "sentiment_score": round(metrics.get("sentiment_score", 0), 4),
                "mentions": int(metrics.get("mentions", 0)),
                "trend_score": round(metrics.get("trend_score", 0), 4),
            }
            entry["success"] = _estimate_success(coin)
            updated.append(entry)

    if updated:
        _write_json_safely(GHOST_LOG_PATH, entries)

    return updated


def get_ghost_performance_ranking() -> List[Dict[str, Any]]:
    entries = _read_json_safely(GHOST_LOG_PATH, default=[])
    if not entries:
        return []

    stats: Dict[str, Dict[str, float]] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        coin = str(e.get("coin", "")).upper()
        if not coin or "success" not in e:
            continue
        stats.setdefault(coin, {"count": 0, "sum": 0.0})
        try:
            stats[coin]["count"] += 1
            stats[coin]["sum"] += float(e.get("success", 0) or 0)
        except Exception:
            pass

    ranking: List[Dict[str, Any]] = []
    for coin, data in stats.items():
        if data["count"] <= 0:
            continue
        avg = data["sum"] / data["count"]
        ranking.append({
            "coin": coin,
            "durchschnitt": round(avg, 3),
            "anzahl": data["count"]
        })

    ranking.sort(key=lambda x: x["durchschnitt"], reverse=True)
    return ranking


def run_ghost_analysis() -> str:
    entries = _read_json_safely(GHOST_LOG_PATH, default=[])
    if not entries:
        return "📭 Keine Einträge im Ghost-Log gefunden."

    stats: Dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        coin = str(entry.get("coin", "")).upper()
        if not coin:
            continue
        stats[coin] = stats.get(coin, 0) + 1

    lines = ["🧠 Ghost-Analyse abgeschlossen:", ""]
    for coin, count in sorted(stats.items(), key=lambda x: x[0]):
        lines.append(f"• {coin}: {count} Trades")

    return "\n".join(lines)
