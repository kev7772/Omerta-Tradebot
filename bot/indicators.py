import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

def calculate_indicators(df):
    """
    Erwartet einen DataFrame mit Spalten: open, high, low, close, volume
    Gibt ein Dictionary mit Indikatoren zurück.
    """
    result = {}

    # Schutz gegen ungültige Daten
    if df is None or df.empty or "close" not in df.columns:
        return {"error": "Ungültiger DataFrame"}

    try:
        # RSI
        rsi = RSIIndicator(close=df["close"], window=14)
        result["rsi"] = rsi.rsi().iloc[-1]

        # EMA 20 & 50
        ema20 = EMAIndicator(close=df["close"], window=20).ema_indicator().iloc[-1]
        ema50 = EMAIndicator(close=df["close"], window=50).ema_indicator().iloc[-1]
        result["ema20"] = ema20
        result["ema50"] = ema50

        # MACD
        macd = MACD(close=df["close"])
        result["macd"] = macd.macd().iloc[-1]
        result["macd_signal"] = macd.macd_signal().iloc[-1]

        # Bollinger Bands
        bb = BollingerBands(close=df["close"], window=20, window_dev=2)
        result["bb_upper"] = bb.bollinger_hband().iloc[-1]
        result["bb_lower"] = bb.bollinger_lband().iloc[-1]
        result["bb_percent"] = bb.bollinger_pband().iloc[-1]

    except Exception as e:
        result["error"] = f"Fehler bei Berechnung: {e}"

    return result


def evaluate_indicators(indicators):
    """
    Bewertet ein Indikator-Dictionary als bullish, bearish oder neutral.
    Rückgabe: string "bullish", "bearish" oder "neutral"
    """
    if "error" in indicators:
        return "unbekannt"

    score = 0

    # RSI
    if indicators["rsi"] > 70:
        score -= 1  # überkauft
    elif indicators["rsi"] < 30:
        score += 1  # überverkauft

    # EMA Cross
    if indicators["ema20"] > indicators["ema50"]:
        score += 1
    else:
        score -= 1

    # MACD
    if indicators["macd"] > indicators["macd_signal"]:
        score += 1
    else:
        score -= 1

    # Bollinger Band Auswertung (optional)
    if indicators["bb_percent"] > 0.9:
        score -= 0.5
    elif indicators["bb_percent"] < 0.1:
        score += 0.5

    if score >= 2:
        return "bullish"
    elif score <= -2:
        return "bearish"
    else:
        return "neutral"
