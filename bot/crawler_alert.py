import json
import os
from datetime import datetime

def detect_hype_signals():
    try:
        if not os.path.exists("crawler_data.json"):
            return []

        with open("crawler_data.json", "r") as f:
            data = json.load(f)

        hype_alerts = []
        for entry in data:
            if not isinstance(entry, dict):
                continue  # Schutz vor Strings etc.

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

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[HypeDetect] Fehler: {e}")
        return []


def detect_manipulation_signals():
    try:
        if not os.path.exists("crawler_data.json"):
            return []

        with open("crawler_data.json", "r") as f:
            data = json.load(f)

        suspicious = []
        for entry in data:
            if not isinstance(entry, dict):
                continue  # Schutz vor Strings etc.

            score = entry.get("trend_score", 0)
            mentions = entry.get("mentions", 0)
            social_push = entry.get("social_signal", 0)

            if score > 8 and social_push > 5:
                suspicious.append({
                    "coin": entry.get("coin", "unbekannt"),
                    "score": score,
                    "social": social_push,
                    "timestamp": entry.get("timestamp", datetime.now().isoformat())
                })

        return suspicious

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ManipulationDetect] Fehler: {e}")
        return []
