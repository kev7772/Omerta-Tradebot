# logic.py — OmertaTradeBot: Entscheidungs- und Analyse-Logik (All-Coins-Version)

from __future__ import annotations
from typing import List, Dict, Tuple, Any, Optional
import os
import json

from trading import get_profit_estimates, list_all_tradeable_coins
from sentiment_parser import get_sentiment_data
from crawler import get_crawler_data
from ghost_mode import detect_stealth_entry
from ki_features import _rsi, _ema, _pct, load_json
from ki_model import predict_live

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
    if isinstance(sent, str):
        s = sent.strip().lower()
        return s if s in {"bullish", "bearish", "neutral"} else "neutral"

    if isinstance(sent, dict):
        v = sent.get("sentiment")
        if isinstance(v, str) and v.strip().lower() in {"bullish", "bearish", "neutral"}:
            return v.strip().lower()
        market = sent.get("market") or sent.get("meta")
        if isinstance(market, dict):
            v2 = market.get("sentiment")
            if isinstance(v2, str) and v2.strip().lower() in {"bullish", "bearish", "neutral"}:
                return v2.strip().lower()
    return "neutral"


def _get_coin_sentiment_score(coin: str, sent: Any) -> Optional[float]:
    if not isinstance(sent, dict):
        return None
    coins = sent.get("coins")
    if isinstance(coins, dict):
        c = coins.get(coin)
        if isinstance(c, dict):
            score = c.get("score")
            if isinstance(score, (int, float)):
                return float(score)
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
        percent = float(p.get("percent", 0.0))
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
        percent = float(p.get("percent", 0.0))

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

        else:
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
        percent = float(p.get("percent", 0.0))

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

        else:
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
    if not os.path.exists(filepath):
        return "❌ Noch kein Lernverlauf vorhanden."

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return "⚠️ Lernlog-Datei beschädigt oder nicht lesbar."

    if not isinstance(data, list) or not data:
        return "📘 Lernlog ist leer."

    output = "📘 Lernverlauf (letzte 5 Einträge):\n"
    for eintrag in data[-5:]:
        datum = eintrag.get("date") or eintrag.get("evaluated_at") or "???"
        coin = eintrag.get("coin", "???")
        erfolg = eintrag.get("success") or eintrag.get("success_rate") or "?"
        if isinstance(erfolg, (int, float)):
            erfolg = f"{float(erfolg):.1f}"
        output += f"📅 {datum} | {coin} | Erfolg: {erfolg}%\n"
    return output


# =========================
# Ghost-Analyse Wrapper
# =========================
def run_ghost_analysis() -> list:
    profits = get_profit_estimates() or []
    sentiment = get_sentiment_data()
    crawler_data = get_crawler_data() or {}
    return detect_stealth_entry(profits, sentiment, crawler_data)


# =========================
# KI-Score-Berechnung
# =========================
def build_live_features(coin, last_prices, crawler_coin, senti_coin):
    curr = last_prices[-1]
    rsi = _rsi(last_prices[-30:])
    ema12 = _ema(last_prices[-30:], 12)
    ema26 = _ema(last_prices[-60:], 26)
    macd = (ema12 or curr) - (ema26 or curr)
    ret_1h = _pct(last_prices[-1], last_prices[-2]) if len(last_prices) >= 2 else 0
    ret_6h = _pct(last_prices[-1], last_prices[-7]) if len(last_prices) >= 7 else 0
    ret_24h = _pct(last_prices[-1], last_prices[-25]) if len(last_prices) >= 25 else 0
    vol_trend = (crawler_coin or {}).get("trend_score", 0.0)
    mentions = (crawler_coin or {}).get("mentions", 0)
    senti_score = (senti_coin or {}).get("score", 0.0)
    return [curr, rsi or 50.0, macd, ret_1h, ret_6h, ret_24h, vol_trend, mentions, senti_score]

def get_ki_score_for_coin(coin):
    hist = load_json("history.json")
    if not hist:
        return 0.5
    ts = sorted(hist.keys())[-30:]
    prices = [hist[t].get(coin) for t in ts if coin in hist[t]]
    if len(prices) < 30:
        return 0.5
    crawler = load_json("crawler_data.json").get(coin, {})
    senti = load_json("sentiment_snapshot.json").get(coin, {})
    row = build_live_features(coin, prices, crawler, senti)
    return predict_live(row)
