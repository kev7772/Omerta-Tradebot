# crawler_alert.py — Hype & Manipulation Alerts auf Basis echter Crawler-Daten
# Stand: 2025-08-10

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

CRAWLER_FILE = "crawler_data.json"

# ---------------------------
# Konfiguration / Schwellen
# ---------------------------
MIN_MENTIONS_HYPE = 50         # ab so vielen "mentions" (aus coins-Liste) prüfen wir intensiver
MIN_TREND_SCORE_HYPE = 0.60    # 0..1 — ab diesem Trendscore → Hype-Kandidat
TITLE_HYPE_KEYWORDS = (
    "allzeithoch", "breakout", "to the moon", "parabolic", "approval", "listing", "partnership",
    "bull", "rally", "surges", "soars", "records high", "ath"
)
TITLE_MANIPULATION_KEYWORDS = (
    "pump", "pump&dump", "pump and dump", "signal", "call", "insider", "manipulation", "rug", "rugpull",
    "scheme", "coordinated", "shill", "brigade"
)
TITLE_NEGATIVE_KEYWORDS = (
    "dump", "crash", "hack", "exploit", "scam", "fraud", "lawsuit", "ban", "verbot", "liquidation",
    "delist", "probe", "investigation"
)

# ---------------------------
# Utils
# ---------------------------
def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _load_crawler() -> Dict[str, Any]:
    if not os.path.exists(CRAWLER_FILE):
        return {}
    try:
        with open(CRAWLER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[CrawlerAlert] Laden fehlgeschlagen: {e}")
        return {}

def _lc_titles(payload: Dict[str, Any]) -> List[str]:
    titles = (payload.get("raw", {}) or {}).get("titles", []) or []
    return [str(t).strip().lower() for t in titles if str(t).strip()]

def _coin_hits_in_titles(coin: str, titles_lc: List[str]) -> int:
    # Einfach: prüfe Symbol & häufige Vollnamen
    names = {
        "BTC": ("bitcoin",),
        "ETH": ("ethereum", "ether"),
        "SOL": ("solana",),
        "XRP": ("xrp", "ripple"),
        "DOGE": ("doge", "dogecoin"),
        "BNB": ("bnb", "binance coin"),
        "ADA": ("ada", "cardano"),
        "PEPE": ("pepe",),
    }
    keys = {coin.lower()}
    for k in names.get(coin.upper(), ()):
        keys.add(k)
    text = " • ".join(titles_lc)
    return sum(1 for k in keys if k in text)

def _any_keyword(titles_lc: List[str], keywords: tuple[str, ...]) -> bool:
    blob = " • ".join(titles_lc)
    return any(k in blob for k in keywords)

def _collect_sources(payload: Dict[str, Any]) -> List[str]:
    src = (payload.get("raw", {}) or {}).get("sources", {}) or {}
    out = []
    for k, v in src.items():
        if v:
            out.append(k)
    return out or ["rss"]  # Minimal

# ---------------------------
# Hauptlogik
# ---------------------------
def detect_hype_signals() -> List[Dict[str, Any]]:
    """
    Erkennt Hype-Kandidaten:
      - coins[].mentions >= MIN_MENTIONS_HYPE ODER coins[].trend_score >= MIN_TREND_SCORE_HYPE
      - UND mindestens 1 Treffer in Headlines (Coinname/Symbol oder typische Hype-Wörter)
    Gibt Liste von Dicts zurück: {coin, hype_score, reasons[], sources[], timestamp}
    """
    payload = _load_crawler()
    if not payload:
        return []

    titles_lc = _lc_titles(payload)
    coins = payload.get("coins", []) or []
    sources = _collect_sources(payload)
    ts = payload.get("timestamp") or _utc_iso()

    alerts: List[Dict[str, Any]] = []

    for c in coins:
        if not isinstance(c, dict):
            continue
        coin = str(c.get("coin", "")).upper().strip()
        mentions = int(c.get("mentions", 0) or 0)
        tscore = float(c.get("trend_score", 0.0) or 0.0)

        is_candidate = (mentions >= MIN_MENTIONS_HYPE) or (tscore >= MIN_TREND_SCORE_HYPE)
        if not is_candidate:
            continue

        hits_coin = _coin_hits_in_titles(coin, titles_lc)
        hits_hype = _any_keyword(titles_lc, TITLE_HYPE_KEYWORDS)

        if hits_coin == 0 and not hits_hype:
            # keine Unterstützung durch Headlines → kein Hype
            continue

        # einfacher Hype-Score: gewichtete Summe
        hype_score = round(0.6 * (mentions / 100.0) + 0.4 * tscore + 0.2 * min(hits_coin, 3), 3)

        reasons = []
        if mentions >= MIN_MENTIONS_HYPE:
            reasons.append(f"mentions={mentions}")
        if tscore >= MIN_TREND_SCORE_HYPE:
            reasons.append(f"trend_score={tscore:.2f}")
        if hits_coin > 0:
            reasons.append(f"headlines_coin_hits={hits_coin}")
        if hits_hype:
            reasons.append("headlines_hype_keywords")

        alerts.append({
            "coin": coin or "UNKWN",
            "hype_score": hype_score,
            "reasons": reasons,
            "sources": sources,
            "timestamp": ts,
        })

    # nach Relevanz sortieren
    alerts.sort(key=lambda a: a["hype_score"], reverse=True)
    return alerts


def detect_manipulation_signals() -> List[Dict[str, Any]]:
    """
    Erkennt potenzielle Manipulationen („Pump / Signal / Rug …“) anhand echter Headlines.
    Gibt Liste von Dicts zurück: {coin (optional), evidence[], sources[], timestamp}
    """
    payload = _load_crawler()
    if not payload:
        return []

    titles_lc = _lc_titles(payload)
    sources = _collect_sources(payload)
    ts = payload.get("timestamp") or _utc_iso()

    evidence_flags = []
    if _any_keyword(titles_lc, TITLE_MANIPULATION_KEYWORDS):
        evidence_flags.append("manipulation_keywords")
    if _any_keyword(titles_lc, TITLE_NEGATIVE_KEYWORDS):
        evidence_flags.append("negative_risk_keywords")

    if not evidence_flags:
        return []

    # Versuche, betroffene Coins aus den Headlines zu mappen (heuristisch)
    suspects: List[str] = []
    for sym in ("BTC", "ETH", "SOL", "XRP", "DOGE", "BNB", "ADA", "PEPE"):
        if _coin_hits_in_titles(sym, titles_lc) > 0:
            suspects.append(sym)

    return [{
        "coin": suspects or None,
        "evidence": evidence_flags,
        "sources": sources,
        "timestamp": ts,
    }]
