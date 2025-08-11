# ki_model.py
import os, json, pickle, time
from pathlib import Path
from datetime import datetime, timezone
from ki_features import build_dataset, load_json

MODEL_DIR = "models"
MODEL_PATH = f"{MODEL_DIR}/ki_model.pkl"
METRICS_PATH = f"{MODEL_DIR}/ki_metrics.json"
SENTI_SNAPSHOT = "sentiment_snapshot.json"

def save_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p,"w") as f: json.dump(obj, f, indent=2, ensure_ascii=False)

def train_model():
    # sentiment snapshot speichern (damit Features reproduzierbar)
    try:
        from sentiment_parser import get_sentiment_data
        save_json(SENTI_SNAPSHOT, get_sentiment_data())
    except Exception:
        save_json(SENTI_SNAPSHOT, {})

    X, y, _ = build_dataset()
    if len(X) < 200:
        return {"ok": False, "msg": "Zu wenig Trainingsdaten"}

    # kleiner RandomForest (keine Zusatz-Dep)
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import roc_auc_score, accuracy_score
    import numpy as np

    clf = RandomForestClassifier(
        n_estimators=120, max_depth=8, min_samples_leaf=5, random_state=42, n_jobs=-1
    )
    # einfacher Train/Test Split
    split = int(len(X)*0.8)
    Xtr, Xte = np.array(X[:split]), np.array(X[split:])
    ytr, yte = np.array(y[:split]), np.array(y[split:])

    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:,1]
    auc = float(roc_auc_score(yte, proba)) if len(set(yte))>1 else None
    acc = float(accuracy_score(yte, (proba>0.5).astype(int)))

    Path(MODEL_DIR).mkdir(exist_ok=True)
    with open(MODEL_PATH,"wb") as f: pickle.dump(clf, f)

    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": len(X),
        "auc": auc, "accuracy": acc
    }
    save_json(METRICS_PATH, metrics)
    return {"ok": True, **metrics}

def predict_live(feature_row):
    import numpy as np, pickle
    if not Path(MODEL_PATH).exists(): 
        return 0.5
    with open(MODEL_PATH,"rb") as f: clf = pickle.load(f)
    return float(clf.predict_proba(np.array([feature_row]))[0,1])
