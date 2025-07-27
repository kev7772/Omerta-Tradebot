import json
from datetime import datetime

def detect_hype_signals():
    try:
        with open("crawler_data.json", "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    hype_alerts = []
    for entry in data:
        score = entry.get("trend_score", 0)
        sources = entry.get("sources", [])
        if score > 7 and any("reddit" in s or "twitter" in s for s in sources):
            hype_alerts.append({
                "coin": entry.get("coin", "unbekannt"),
                "score": score,
                "sources": sources,
                "timestamp": entry.get("timestamp", datetime.now().isoformat())
            })

    return hype_alerts
