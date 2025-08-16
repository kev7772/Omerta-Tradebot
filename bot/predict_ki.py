# predict_ki.py — KI-Vorhersage für OmertaTradeBot
# Lädt trainiertes Modell + Scaler, berechnet Erfolgswahrscheinlichkeit für einen Coin.

import json, math, pickle
from datetime import datetime, timedelta
from pathlib import Path

MODELS_DIR   = Path("models")
MODEL_PATH   = MODELS_DIR / "ki_model.pkl"
SCALER_PATH  = MODELS_DIR / "ki_scaler.pkl"
METRICS_PATH = MODELS_DIR / "ki_metrics.json"

HISTORY_PATH = Path("history.json")

# ---------- Utils ----------
def _parse_dt(s: str):
    if not s:
        return None
    s = str(s).split("+")[0].split("Z")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None

def _load_json_safe(path: Path, default):
    try:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _history_to_timeseries(history):
    out = {}
    if not isinstance(history, list):
        return out
    for snap in history:
        t_raw = snap.get("time") or snap.get("timestamp") or snap.get("ts")
        t = _parse_dt(t_raw)
        if not t:
            continue
        prices = snap.get("prices") or snap.get("data") or {}
        if isinstance(prices, list):
            for p in prices:
                coin = p.get("coin")
                price = p.get("price")
                if coin and isinstance(price, (int, float)):
                    out.setdefault(str(coin).upper(), []).append((t, float(price)))
        elif isinstance(prices, dict):
            for coin, price in prices.items():
                if isinstance(price, (int, float)):
                    out.setdefault(str(coin).upper(), []).append((t, float(price)))
    for c in out:
        out[c].sort(key=lambda x: x[0])
    return out

def _window_stats(series_tp, t_center: datetime, hours: int = 24):
    if not series_tp or not t_center:
        return None, None
    t_min = t_center - timedelta(hours=hours)
    window = [(t, p) for (t, p) in series_tp if t_min <= t <= t_center]
    if len(window) < 2:
        return None, None
    window.sort(key=lambda x: x[0])
    prices = [p for (_, p) in window if isinstance(p, (int, float))]
    if len(prices) < 2 or prices[0] <= 0:
        return None, None
    ret_24 = (prices[-1] / prices[0]) - 1.0
    logrets = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        if prev > 0 and cur > 0:
            logrets.append(math.log(cur / prev))
    if not logrets:
        vol_24 = 0.0
    else:
        mean_lr = sum(logrets) / len(logrets)
        var = sum((x - mean_lr) ** 2 for x in logrets) / max(1, (len(logrets) - 1))
        vol_24 = math.sqrt(var)
    return ret_24, vol_24

# ---------- Prediction ----------
def predict_success(coin: str):
    """
    Gibt Erfolgswahrscheinlichkeit (0–1) für einen Coin zurück
    """
    coin = str(coin).upper()
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        return {"error": "Kein trainiertes Modell vorhanden. Bitte erst trainieren (train_ki_model.py)."}

    # Lade Modell + Scaler
    with open(MODEL_PATH, "rb") as f:
        clf = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)

    # Lade History
    hist = _load_json_safe(HISTORY_PATH, [])
    ts   = _history_to_timeseries(hist)
    series_tp = ts.get(coin)
    if not series_tp:
        return {"error": f"Keine Preisdaten für {coin} gefunden."}

    # Features berechnen
    now = series_tp[-1][0]  # letztes Datum als Referenz
    r24, v24 = _window_stats(series_tp, now, hours=24)
    if r24 is None or v24 is None:
        return {"error": f"Nicht genug Daten für {coin} (24h-Fenster)."}

    X = [[r24, v24]]
    Xs = scaler.transform(X)
    prob = clf.predict_proba(Xs)[0, 1]
    pred = clf.predict(Xs)[0]

    return {
        "coin": coin,
        "probability_success": round(float(prob), 4),
        "prediction": int(pred),
        "features": {"ret_24h": r24, "vol_24h": v24},
        "evaluated_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }

if __name__ == "__main__":
    print(predict_success("BTC"))
