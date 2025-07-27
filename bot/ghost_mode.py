import json
from datetime import datetime
from sentiment_parser import get_sentiment_data
from trading import get_profit_estimates
from crawler import get_crawler_data

GHOST_LOG_PATH = "ghost_log.json"

def detect_stealth_entry(profit_data, sentiment_data, crawler_data):
    entries = []
    for p in profit_data:
        coin = p["coin"]
        percent = p["percent"]
        sentiment = sentiment_data.get(coin, {})
        mentions = crawler_data.get(coin, {}).get("mentions", 0)
        trend_score = crawler_data.get(coin, {}).get("trend_score", 0)

        if (
            percent < 2 and
            mentions < 50 and
            sentiment.get("score", 0) > 0.6 and
            trend_score > 0.4
        ):
            entries.append({
                "coin": coin,
                "reason": "Ghost Entry: Ruhiger Markt, frühes Sentiment, kein Social-Hype",
                "time": datetime.now().isoformat()
            })
    return entries

def run_ghost_mode():
    profits = get_profit_estimates()
    sentiment = get_sentiment_data()
    crawler_data = get_crawler_data()
    new_entries = detect_stealth_entry(profits, sentiment, crawler_data)

    if new_entries:
        try:
            with open(GHOST_LOG_PATH, "r") as f:
                log = json.load(f)
        except:
            log = []

        log.extend(new_entries)

        with open(GHOST_LOG_PATH, "w") as f:
            json.dump(log, f, indent=2)

    return new_entries
