import json
from sentiment_parser import get_sentiment_data
from trading import get_profit_estimates
from crawler import get_crawler_data

def detect_stealth_entry(profit_data, sentiment_data, crawler_data):
    stealth_entries = []

    for p in profit_data:
        coin = p['coin']
        percent = p['percent']
        sentiment = sentiment_data.get(coin, {})
        mentions = crawler_data.get(coin, {}).get('mentions', 0)
        trend_score = crawler_data.get(coin, {}).get('trend_score', 0)

        if (
            percent < 2 and  # Preis ruhig
            mentions < 50 and  # Kein Social-Hype
            sentiment.get('score', 0) > 0.6 and  # Positiver Shift
            trend_score > 0.4  # Frühindikator aus Trends
        ):
            stealth_entries.append({
                'coin': coin,
                'reason': 'Ghost Entry: Low price action, early sentiment rise, no herd activity'
            })

    return stealth_entries
