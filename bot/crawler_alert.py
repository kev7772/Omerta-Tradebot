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

def detect_manipulation_signals():
    try:
        with open("crawler_data.json", "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    suspicious = []
    for entry in data:
        score = entry.get("trend_score", 0)
        mentions = entry.get("mentions", 0)
        social_push = entry.get("social_signal", 0)  # z. B. Retweets, Upvotes etc.

        if score > 8 and social_push > 5:
            suspicious.append({
                "coin": entry.get("coin", "unbekannt"),
                "score": score,
                "social": social_push,
                "timestamp": entry.get("timestamp")
            })

    return suspicious
