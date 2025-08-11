# ki_features.py
import json, math
from datetime import datetime, timezone
from pathlib import Path

HISTORY_FILE = "history.json"
CRAWLER_FILE = "crawler_data.json"
SENTI_FILE = "sentiment_snapshot.json"  # lege ich beim Training on-the-fly ab

def _rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d,0)); losses.append(abs(min(d,0)))
    if len(gains) < period: return None
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period or 1e-9
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def _ema(prices, span=12):
    if not prices: return None
    k = 2/(span+1)
    ema = prices[0]
    for p in prices[1:]:
        ema = p*k + ema*(1-k)
    return ema

def _pct(a,b): 
    if b==0: return 0.0
    return (a-b)/b*100.0

def load_json(path):
    if not Path(path).exists(): return {}
    with open(path,"r") as f: 
        try: return json.load(f)
        except: return {}

def build_dataset(horizon_hours=6, min_history=60):
    """Erzeugt X,y pro Coin aus history + optional crawler + sentiment."""
    history = load_json(HISTORY_FILE)  # {date_iso: {COIN: price_eur, ...}, ...}
    crawler = load_json(CRAWLER_FILE)  # {COIN: {...}}
    senti = load_json(SENTI_FILE)      # {COIN: {"score":..}, ...}

    # sort timestamps
    ts = sorted(history.keys())
    if len(ts) < min_history: return [],[],[]
    # make per-coin series
    coins = set()
    for t in ts: coins.update(history[t].keys())

    X, y, meta = [], [], []  # meta hält (coin, timestamp)
    for coin in coins:
        prices = [(t, history[t].get(coin)) for t in ts if coin in history[t]]
        prices = [(datetime.fromisoformat(t), p) for t,p in prices if p is not None]
        if len(prices) < min_history: continue
        closes = [p for _,p in prices]
        for i in range(min_history, len(closes)-horizon_hours):
            window = closes[:i+1]
            curr = window[-1]
            future = closes[i+horizon_hours]
            rsi = _rsi(window[-30:])      # RSI(14) aus letzten 30
            ema12 = _ema(window[-30:], 12)
            ema26 = _ema(window[-60:], 26)
            macd = (ema12 or curr) - (ema26 or curr)
            ret_1h = _pct(window[-1], window[-2]) if len(window) >=2 else 0
            ret_6h = _pct(window[-1], window[-7]) if len(window) >=7 else 0
            ret_24h= _pct(window[-1], window[-25]) if len(window) >=25 else 0
            vol_trend = crawler.get(coin, {}).get("trend_score", 0.0)
            mentions = crawler.get(coin, {}).get("mentions", 0)
            senti_score = (senti.get(coin, {}) or {}).get("score", 0.0)

            feat = [
                curr, rsi or 50.0, macd, ret_1h, ret_6h, ret_24h,
                vol_trend, mentions, senti_score
            ]
            X.append(feat)
            y.append(1 if future > curr else 0)
            meta.append((coin, prices[i][0].isoformat()))
    return X, y, meta
