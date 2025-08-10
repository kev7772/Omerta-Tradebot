# indicators.py
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
from typing import Dict, Any

def calculate_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Erwartet einen DataFrame mit Spalten: open, high, low, close, volume
    Gibt ein Dictionary mit RSI, EMA20, EMA50, MACD, MACD-Signal, Bollinger Bändern zurück.
    """
    result = {}

    # Schutz gegen ungültige Daten
    if df is None or df.empty or "close" not in df.columns:
        return {"error": "Ungültiger DataFrame"}

    try:
        # RSI
        rsi = RSIIndicator(close=df["close"], window=14)
        result["rsi"] = float(rsi.rsi().iloc[-1])

        # EMA 20 & 50
        ema20 = EMAIndicator(close=df["close"], window=20).ema_indicator().iloc[-1]
        ema50 = EMAIndicator(close=df["close"], window=50).ema_indicator().iloc[-1]
        result["ema20"] = float(ema20)
        result["ema50"] = float(ema50)

        # MACD
        macd = MACD(close=df["close"])
        result["macd"] = float(macd.macd().iloc[-1])
        result["macd_signal"] = float(macd.macd_signal().iloc[-1])

        # Bollinger Bands
        bb = BollingerBands(close=df["close"], window=20, window_dev=2)
        result["bb_upper"] = float(bb.bollinger_hband().iloc[-1])
        result["bb_lower"] = float(bb.bollinger_lband().iloc[-1])
        result["bb_percent"] = float(bb.bollinger_pband().iloc[-1])

    except Exception as e:
        result["error"] = f"Fehler bei Berechnung: {e}"

    return result


def evaluate_indicators(indicators: Dict[str, Any]) -> str:
    """
    Bewertet ein Indikator-Dictionary als bullish, bearish oder neutral.
    Rückgabe: "bullish", "bearish" oder "neutral".
    """
    if not indicators or "error" in indicators:
        return "unbekannt"

    score = 0

    # RSI
    if indicators.get("rsi", 50) > 70:
        score -= 1  # überkauft
    elif indicators.get("rsi", 50) < 30:
        score += 1  # überverkauft

    # EMA Cross
    if indicators.get("ema20", 0) > indicators.get("ema50", 0):
        score += 1
    else:
        score -= 1

    # MACD
    if indicators.get("macd", 0) > indicators.get("macd_signal", 0):
        score += 1
    else:
        score -= 1

    # Bollinger Band Position
    bb_percent = indicators.get("bb_percent", 0.5)
    if bb_percent > 0.9:
        score -= 0.5
    elif bb_percent < 0.1:
        score += 0.5

    if score >= 2:
        return "bullish"
    elif score <= -2:
        return "bearish"
    else:
        return "neutral"
