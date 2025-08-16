# train_ki_model.py — echtes KI-Training für OmertaTradeBot
# Nutzt learning_log.json + history.json, trainiert LogisticRegression,
# speichert Modelle & Metriken unter models/

import os, json, math
from datetime import datetime, timedelta
from pathlib import Path

MODELS_DIR = Path("models")
METRICS_PATH = MODELS_DIR / "ki_metrics.json"
MODEL_PATH = MODELS_DIR / "ki_model.pkl"
SCALER_PATH = MODELS_DIR / "ki_scaler.pkl"

HISTORY_PATH = Path("history.json")          # Zeitreihe der Preise
LEARN_LOG_PATH = Path("learning_log.json")   # Einträge mit success (%), coin, date

def _ensure_models_dir():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

def _parse_dt(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.split("+")[0].split("Z")[0], fmt)
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
    """
    Versucht robuste Struktur:
    - Liste von Snapshots.
      Jeder Snapshot kann entweder
        {"time":"...","prices":[{"coin":"BTC","price":...}, ...]}
      oder {"time":"...","prices":{"BTC": 12345, ...}}
      oder {"timestamp":"...","prices":...}
    Gibt dict: coin -> Liste[(t, price)] (zeitlich sortiert) zurück.
    """
    out = {}
    if not isinstance(history, list):
        return out
    for snap in history:
        t_raw = snap.get("time") or snap.get("timestamp") or snap.get("ts")
        t = _parse_dt(str(t_raw)) if t_raw else None
        if not t: 
            continue
        prices = snap.get("prices") or snap.get("data") or {}
        if isinstance(prices, list):
            for p in prices:
                coin = str(p.get("coin")).upper() if p.get("coin") else None
                price = p.get("price")
                if coin and isinstance(price, (int,float)):
                    out.setdefault(coin, []).append((t, float(price)))
        elif isinstance(prices, dict):
            for coin, price in prices.items():
                if isinstance(price, (int,float)):
                    out.setdefault(str(coin).upper(), []).append((t, float(price)))
    # sortieren
    for c in out:
        out[c].sort(key=lambda x: x[0])
    return out

def _window_stats(series, t_center: datetime, hours: int = 24):
    """
    Nimmt Liste[(t, price)] und liefert Return & Volatilität über das Fenster [t_center-hours, t_center]
    """
    if not series:
        return None, None
    t_min = t_center - timedelta(hours=hours)
    points = [p for (t,p) in series if t_min <= t <= t_center]
    if len(points) < 2:
        return None, None
    start, end = points[0], points[-1]
    ret = (end - start) / start if start else 0.0
    # einfache Volatilität (Std der log-Returns)
    logrets = []
    prev = points[0]
    for cur in points[1:]:
        if prev > 0 and cur > 0:
            logrets.append(math.log(cur/prev))
        prev = cur
    vol = (sum((x - (sum(logrets)/len(logrets)))**2 for x in logrets)/max(1,(len(logrets)-1)))**0.5 if logrets else 0.0
    return ret, vol

def build_dataset():
    """
    Baut X, y aus learning_log.json (& history.json).
    y = 1, wenn success > 0 sonst 0
    Features:
      - ret_24h (Preisänderung bis zum Datum)
      - vol_24h (Volatilität bis zum Datum)
    """
    learn = _load_json_safe(LEARN_LOG_PATH, [])
    hist = _load_json_safe(HISTORY_PATH, [])
    ts = _history_to_timeseries(hist)

    X, y = [], []
    samples = 0
    for row in learn if isinstance(learn, list) else []:
        coin = str(row.get("coin", "")).upper()
        date = row.get("date") or row.get("evaluated_at") or row.get("time")
        success = row.get("success")
        if not coin or success is None:
            continue
        t = _parse_dt(str(date))
        if not t:
            continue
        series = ts.get(coin)
        r24, v24 = _window_stats([p for (_,p) in series] if series else [], t, hours=24)
        if r24 is None or v24 is None:
            # Versuch: nutze alle Coins als Fallback
            # (macht die Features generischer, wenn coin-spez. Historie fehlt)
            all_prices = []
            for c in ts.values():
                all_prices.extend([p for (_,p) in c])
            if len(all_prices) > 5:
                # grober Fallback
                r24, v24 = 0.0, 0.0
            else:
                continue
        X.append([r24, v24])
        y.append(1 if float(success) > 0 else 0)
        samples += 1

    return X, y, samples

def train_model():
    _ensure_models_dir()

    # Versuche echtes Training
    try:
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, roc_auc_score
        import pickle

        X, y, n = build_dataset()
        if n < 20 or len(set(y)) < 2:
            # Zu wenig oder nur eine Klasse → Metriken aus Lernlog ableiten
            acc = (sum(y)/len(y)) if y else 0.0
            metrics = {
                "n_samples": n,
                "auc": None,
                "accuracy": round(float(acc), 4),
                "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "Zu wenige/ungleiche Klassen – kein Modell trainiert, nur Kennzahl aus Lernlog."
            }
            with METRICS_PATH.open("w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)
            return metrics

        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        clf = LogisticRegression(max_iter=200)
        clf.fit(Xs, y)

        # In-Sample-Metriken (ok für erste Version)
        pred = clf.predict(Xs)
        probs = clf.predict_proba(Xs)[:,1]
        acc = accuracy_score(y, pred)
        try:
            auc = roc_auc_score(y, probs)
        except Exception:
            auc = None

        # speichern
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
        pos = sum(1 for r in learn if float(r.get("success", 0)) > 0) if isinstance(learn, list) else 0
        n = len(learn) if isinstance(learn, list) else 0
        acc = (pos / n) if n > 0 else 0.0
        metrics = {
            "n_samples": n,
            "auc": None,
            "accuracy": round(float(acc), 4),
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "note": "scikit-learn nicht installiert – bitte in requirements aufnehmen."
        }
        _ensure_models_dir()
        with METRICS_PATH.open("w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        return metrics

if __name__ == "__main__":
    m = train_model()
    print("[KI] Train completed:", m)
