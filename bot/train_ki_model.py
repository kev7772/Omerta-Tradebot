# train_ki_model.py — echtes KI-Training für OmertaTradeBot
# Nutzt learning_log.json + history.json, trainiert LogisticRegression,
# speichert Modelle & Metriken unter models/
# — Auto-Ordner-Erstellung + robuste Window-Stats —

import os, json, math, pickle
from datetime import datetime, timedelta
from pathlib import Path

MODELS_DIR = Path("models")
METRICS_PATH = MODELS_DIR / "ki_metrics.json"
MODEL_PATH   = MODELS_DIR / "ki_model.pkl"
SCALER_PATH  = MODELS_DIR / "ki_scaler.pkl"

HISTORY_PATH   = Path("history.json")         # Zeitreihe der Preise
LEARN_LOG_PATH = Path("learning_log.json")    # Einträge mit success (%), coin, date

# ---------- Utils ----------
def _ensure_models_dir():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

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

# ---------- History: in Timeseries umwandeln ----------
def _history_to_timeseries(history):
    """
    Erwartet eine Liste von Snapshots:
      {"time": "...", "prices":[{"coin":"BTC","price":...}, ...]}   ODER
      {"time": "...", "prices":{"BTC": 12345, ...}}                 ODER
      {"timestamp": "...", ...}
    Rückgabe: dict coin -> Liste[(t, price)] (t aufsteigend sortiert)
    """
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
                    coin = str(coin).upper()
                    out.setdefault(coin, []).append((t, float(price)))
        elif isinstance(prices, dict):
            for coin, price in prices.items():
                if isinstance(price, (int, float)):
                    out.setdefault(str(coin).upper(), []).append((t, float(price)))
    # sortieren
    for c in out:
        out[c].sort(key=lambda x: x[0])
    return out

def _window_stats(series_tp, t_center: datetime, hours: int = 24):
    """
    series_tp: Liste[(t, price)]
    Liefert: (ret_24h, vol_24h) im Fenster [t_center-hours, t_center]
    - ret_24h: (last/first - 1)
    - vol_24h: Std-Abw. der Log-Returns innerhalb des Fensters
    """
    if not series_tp or not t_center:
        return None, None
    t_min = t_center - timedelta(hours=hours)
    window = [(t, p) for (t, p) in series_tp if t_min <= t <= t_center]
    if len(window) < 2:
        return None, None

    # Preise extrahieren, nach Zeit sortiert
    window.sort(key=lambda x: x[0])
    prices = [p for (_, p) in window if isinstance(p, (int, float))]
    if len(prices) < 2 or prices[0] <= 0:
        return None, None

    ret_24 = (prices[-1] / prices[0]) - 1.0

    # Log-Returns für Volatilität
    logrets = []
    for i in range(1, len(prices)):
        prev, cur = prices[i - 1], prices[i]
        if prev > 0 and cur > 0:
            logrets.append(math.log(cur / prev))
    if len(logrets) == 0:
        vol_24 = 0.0
    else:
        mean_lr = sum(logrets) / len(logrets)
        var = sum((x - mean_lr) ** 2 for x in logrets) / max(1, (len(logrets) - 1))
        vol_24 = math.sqrt(var)

    return ret_24, vol_24

# ---------- Dataset bauen ----------
def build_dataset():
    """
    Baut X, y aus learning_log.json (& history.json).
    y = 1, wenn success > 0, sonst 0
    Features:
      - ret_24h (Preisänderung bis zum Datum)
      - vol_24h (Volatilität bis zum Datum)
    """
    learn = _load_json_safe(LEARN_LOG_PATH, [])
    hist  = _load_json_safe(HISTORY_PATH, [])
    ts    = _history_to_timeseries(hist)

    X, y = [], []
    samples = 0

    if not isinstance(learn, list) or not learn:
        return X, y, 0

    for row in learn:
        coin = str(row.get("coin", "")).upper()
        if not coin:
            continue
        date = row.get("date") or row.get("evaluated_at") or row.get("time")
        success = row.get("success")
        if success is None:
            continue
        t = _parse_dt(date)
        if not t:
            continue

        series_tp = ts.get(coin, [])
        r24, v24 = _window_stats(series_tp, t, hours=24)

        if r24 is None or v24 is None:
            # Fallback: kein Sample, wenn wir keine brauchbaren Stats haben
            continue

        X.append([r24, v24])
        y.append(1 if float(success) > 0 else 0)
        samples += 1

    return X, y, samples

# ---------- Training ----------
def train_model():
    _ensure_models_dir()

    # Versuche echtes Training
    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, roc_auc_score

        X, y, n = build_dataset()

        # Falls zu wenig Daten oder nur eine Klasse -> Metriken aus Lernlog ableiten
        if n < 20 or len(set(y)) < 2:
            acc = (sum(y) / len(y)) if y else 0.0
            metrics = {
                "n_samples": n,
                "auc": None,
                "accuracy": round(float(acc), 4),
                "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "Zu wenige/ungleiche Klassen – Modell nicht trainiert, nur Kennzahl aus Lernlog."
            }
            with METRICS_PATH.open("w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
            return metrics

        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)

        clf = LogisticRegression(max_iter=200)
        clf.fit(Xs, y)

        # In-Sample-Metriken (ok für erste Version)
        pred  = clf.predict(Xs)
        probs = clf.predict_proba(Xs)[:, 1]
        acc = accuracy_score(y, pred)
        try:
            auc = roc_auc_score(y, probs)
        except Exception:
            auc = None

        # Modelle speichern
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(clf, f)
        with open(SCALER_PATH, "wb") as f:
            pickle.dump(scaler, f)

        metrics = {
            "n_samples": len(y),
            "auc": round(float(auc), 4) if auc is not None else None,
            "accuracy": round(float(acc), 4),
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with METRICS_PATH.open("w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        return metrics

    except ModuleNotFoundError:
        # sklearn nicht installiert → Dummy-Kennzahlen aus Lernlog
        learn = _load_json_safe(LEARN_LOG_PATH, [])
        n = len(learn) if isinstance(learn, list) else 0
        pos = sum(1 for r in learn if isinstance(r, dict) and float(r.get("success", 0)) > 0) if n else 0
        acc = (pos / n) if n > 0 else 0.0
        metrics = {
            "n_samples": n,
            "auc": None,
            "accuracy": round(float(acc), 4),
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "scikit-learn nicht installiert – bitte in requirements.txt aufnehmen."
        }
        with METRICS_PATH.open("w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        return metrics

if __name__ == "__main__":
    m = train_model()
    print("[KI] Train completed:", m)
