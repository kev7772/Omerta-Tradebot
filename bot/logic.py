# logic.py
# — OmertaTradeBot: Entscheidungs- und Analyse-Logik —
# Robust gegen fehlende/variable Datenstrukturen, mit zentralen Schwellenwerten.

from __future__ import annotations
from typing import List, Dict, Tuple, Any, Optional
import os
import json

from trading import get_profit_estimates
from sentiment_parser import get_sentiment_data
from crawler import get_crawler_data
from ghost_mode import detect_stealth_entry

# =========================
# Zentrale Schwellenwerte
# =========================
PANIC_DROP_PCT = -25.0

BULLISH_SELL_PCT = 20.0
BULLISH_HOLD_FLOOR_PCT = -15.0

BEARISH_SELL_PCT = 12.0

NEUTRAL_SELL_PCT = 18.0
NEUTRAL_HOLD_FLOOR_PCT = -10.0

RECOMMEND_STRONG_GAIN_BULL = 12.0
RECOMMEND_STRONG_LOSS_BULL = -18.0

RECOMMEND_STRONG_GAIN_BEAR = 8.0
RECOMMEND_STRONG_LOSS_BEAR = -10.0

RECOMMEND_STRONG_GAIN_NEUT = 15.0
RECOMMEND_STRONG_LOSS_NEUT = -15.0


# =========================
# Sentiment-Normalisierung
# =========================
def _normalize_market_sentiment(sent: Any) -> str:
    """
    Akzeptiert:
      - "bullish"/"bearish"/"neutral" (str)
      - {"sentiment": "..."} (dict)
      - {"market": {"sentiment": "..."}} (dict)
      - {"scores": {...}, "meta": {"sentiment": "..."}} (dict)
    Fallback auf "neutral".
    """
    if isinstance(sent, str):
        s = sent.strip().lower()
        return s if s in {"bullish", "bearish", "neutral"} else "neutral"

    if isinstance(sent, dict):
        # direkte Angabe
        v = sent.get("sentiment")
        if isinstance(v, str):
            s = v.strip().lower()
            if s in {"bullish", "bearish", "neutral"}:
                return s
        # meta.market
        market = sent.get("market") or sent.get("meta")
        if isinstance(market, dict):
            v2 = market.get("sentiment")
            if isinstance(v2, str):
                s2 = v2.strip().lower()
                if s2 in {"bullish", "bearish", "neutral"}:
                    return s2
    return "neutral"


def _get_coin_sentiment_score(coin: str, sent: Any) -> Optional[float]:
    """
    Versucht, pro-Coin-Sentiment-Score zu holen, falls vorhanden.
    Erwartete mögliche Strukturen:
      - {"coins": {"BTC": {"score": 0.73}, ...}}
      - {"BTC": {"score": 0.73}, ...}
    Rückgabe: float 0..1 oder None.
    """
    if not isinstance(sent, dict):
        return None

    # Variante 1: coins-Bucket
    coins = sent.get("coins")
    if isinstance(coins, dict):
        c = coins.get(coin)
        if isinstance(c, dict):
            score = c.get("score")
            if isinstance(score, (int, float)):
                return float(score)

    # Variante 2: flach pro Coin
    c2 = sent.get(coin)
    if isinstance(c2, dict):
        score = c2.get("score")
        if isinstance(score, (int, float)):
            return float(score)

    return None


# =========================
# Panic-Trigger
# =========================
def should_trigger_panic() -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Prüft, ob irgendein Coin unter den PANIC_DROP_PCT fällt.
    Rückgabe: (True/False, Coin oder None, Prozent oder None)
    """
    profits = get_profit_estimates() or []
    worst = None
    for p in profits:
        try:
            pct = float(p.get("percent", 0.0))
            if worst is None or pct < worst.get("percent", 0.0):
                worst = {"coin": p.get("coin"), "percent": pct}
        except Exception:
            continue

    if worst and worst["percent"] < PANIC_DROP_PCT:
        return True, worst["coin"], worst["percent"]
    return False, None, None


# =========================
# Trading-Decision (Text)
# =========================
def get_trading_decision() -> List[str]:
    profits = get_profit_estimates() or []
    if not profits:
        return ["⚠️ Keine Kursdaten verfügbar"]

    sentiment_info = get_sentiment_data()
    market_sent = _normalize_market_sentiment(sentiment_info)
    decisions: List[str] = []

    if market_sent == "bullish":
        decisions.append("📈 Marktstimmung bullish – mehr Risiko erlaubt.")
    elif market_sent == "bearish":
        decisions.append("📉 Marktstimmung bearish – defensiv agieren.")
    else:
        decisions.append("😐 Neutrale Stimmung – keine großen Bewegungen.")

    for p in profits:
        coin = p.get("coin", "?")
        try:
            percent = float(p.get("percent", 0.0))
        except Exception:
            percent = 0.0

        if percent > RECOMMEND_STRONG_GAIN_NEUT:
            decisions.append(f"{coin}: 🔼 Hätte verkauft (+{percent:.2f}%)")
        elif percent < -10:
            decisions.append(f"{coin}: 🔽 Hätte NICHT gekauft ({percent:.2f}%)")
        else:
            decisions.append(f"{coin}: 🤔 Hätte gehalten ({percent:.2f}%)")

    return decisions


# =========================
# Empfehlungen (Text)
# =========================
def recommend_trades() -> List[str]:
    profits = get_profit_estimates() or []
    if not profits:
        return ["⚠️ Keine Kursdaten verfügbar"]

    sentiment_info = get_sentiment_data()
    market_sent = _normalize_market_sentiment(sentiment_info)
    recommendations: List[str] = []

    for p in profits:
        coin = p.get("coin", "?")
        try:
            percent = float(p.get("percent", 0.0))
        except Exception:
            percent = 0.0

        if market_sent == "bullish":
            if percent > RECOMMEND_STRONG_GAIN_BULL:
                recommendations.append(f"{coin}: ✅ Kauf halten oder Gewinn mitnehmen (+{percent:.2f}%)")
            elif percent < RECOMMEND_STRONG_LOSS_BULL:
                recommendations.append(f"{coin}: ⚠️ Beobachten – trotz bullisher Lage fällt der Kurs ({percent:.2f}%)")
            else:
                recommendations.append(f"{coin}: 🤝 Halten ({percent:.2f}%)")

        elif market_sent == "bearish":
            if percent > RECOMMEND_STRONG_GAIN_BEAR:
                recommendations.append(f"{coin}: 🔼 Gewinn sichern! Markt könnte kippen (+{percent:.2f}%)")
            elif percent < RECOMMEND_STRONG_LOSS_BEAR:
                recommendations.append(f"{coin}: 🚨 Meiden / Risiko ({percent:.2f}%)")
            else:
                recommendations.append(f"{coin}: ⛔ Nicht handeln – Markt unsicher ({percent:.2f}%)")

        else:  # neutral
            if percent > RECOMMEND_STRONG_GAIN_NEUT:
                recommendations.append(f"{coin}: 📈 Verkauf denkbar (+{percent:.2f}%)")
            elif percent < RECOMMEND_STRONG_LOSS_NEUT:
                recommendations.append(f"{coin}: ⚠️ Abwarten oder meiden ({percent:.2f}%)")
            else:
                recommendations.append(f"{coin}: 🤝 Halten ({percent:.2f}%)")

    return recommendations


# =========================
# Maschinen-Entscheidung (BUY/SELL/HOLD als Dict)
# =========================
def make_trade_decision() -> Dict[str, str]:
    profits = get_profit_estimates() or []
    if not profits:
        return {"info": "⚠️ Keine Kursdaten verfügbar"}

    sentiment_info = get_sentiment_data()
    market_sent = _normalize_market_sentiment(sentiment_info)
    decisions: Dict[str, str] = {}

    for p in profits:
        coin = p.get("coin", "?")
        try:
            percent = float(p.get("percent", 0.0))
        except Exception:
            percent = 0.0

        if market_sent == "bullish":
            if percent > BULLISH_SELL_PCT:
                decisions[coin] = "SELL"
            elif percent < BULLISH_HOLD_FLOOR_PCT:
                decisions[coin] = "HOLD"
            else:
                decisions[coin] = "BUY"

        elif market_sent == "bearish":
            if percent > BEARISH_SELL_PCT:
                decisions[coin] = "SELL"
            else:
                decisions[coin] = "HOLD"

        else:  # neutral
            if percent > NEUTRAL_SELL_PCT:
                decisions[coin] = "SELL"
            elif percent < NEUTRAL_HOLD_FLOOR_PCT:
                decisions[coin] = "HOLD"
            else:
                decisions[coin] = "BUY"

    return decisions


# =========================
# Lern-Log Ausgabe
# =========================
def get_learning_log() -> str:
    filepath = os.path.join(os.path.dirname(__file__), "learning_log.json")
    print("🔎 Absoluter Pfad zur Datei:", filepath)

    if not os.path.exists(filepath):
        print("❌ Datei nicht gefunden!")
        return "❌ Noch kein Lernverlauf vorhanden (Datei fehlt)."

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()
            print("📄 Inhalt der Datei (gekürzt):", content[:500] + ("..." if len(content) > 500 else ""))
            if not content:
                return "📘 Lernlog ist leer."
            data = json.loads(content)
    except json.JSONDecodeError:
        print("⚠️ JSON-Fehler!")
        return "⚠️ Lernlog-Datei beschädigt oder leer."
    except Exception as e:
        print("⚠️ Unerwarteter Fehler beim Lesen:", e)
        return "⚠️ Konnte den Lernlog nicht lesen."

    if not isinstance(data, list) or not data:
        return "📘 Lernlog ist leer."

    output = "📘 Lernverlauf (letzte 5 Einträge):\n"
    for eintrag in data[-5:]:
        datum = eintrag.get("date") or eintrag.get("evaluated_at") or "???"
        coin = eintrag.get("coin", "???")
        erfolg = eintrag.get("success") or eintrag.get("success_rate") or "?"
        try:
            if isinstance(erfolg, (int, float)):
                erfolg = f"{float(erfolg):.1f}"
        except Exception:
            pass
        output += f"📅 {datum} | {coin} | Erfolg: {erfolg}%\n"

    print("✅ Ausgabe an Telegram:", output)
    return output


# =========================
# Ghost-Analyse Wrapper
# =========================
def run_ghost_analysis() -> list:
    """
    Ruft die Ghost-Entry-Erkennung auf.
    Erwartet:
      - get_profit_estimates() -> [{coin, percent}, ...]
      - get_sentiment_data() -> kann Markt-Label UND/ODER pro-Coin scores liefern
      - get_crawler_data() -> {COIN: {mentions, trend_score, ...}, ...}
    """
    profits = get_profit_estimates() or []
    sentiment = get_sentiment_data()
    crawler_data = get_crawler_data() or {}

    # Optional: pro-Coin Sentiment-Scores anreichern, falls detect_stealth_entry das nutzt.
    # Wir passen das Format nicht hart an, sondern liefern die Rohdaten weiter.
    return detect_stealth_entry(profits, sentiment, crawler_data)
