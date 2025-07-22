import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

def calculate_indicators(df):
    """
    Erwartet einen DataFrame mit Spalten: open, high, low, close, volume
    """
    result = {}

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

    return result
