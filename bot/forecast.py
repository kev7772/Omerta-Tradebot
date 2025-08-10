import random
import json
from datetime import datetime
from pathlib import Path

FORECAST_LOG = "forecast_log.json"

def forecast_market():
    """
    Simuliert eine einfache Marktprognose (Demo-Zweck).
    Rückgabe: bullish | neutral | bearish
    """
    forecast = random.choices(
        ["bullish", "neutral", "bearish"],
        weights=[0.4, 0.3, 0.3],  # leicht bullischer Bias
        k=1
    )[0]

    # Ausgabe in der Konsole
    print(f"📊 Prognose für Marktstimmung: {forecast}")

    # Prognose + Zeit ins Log schreiben
    entry = {
        "timestamp": datetime.now().isoformat(),
        "forecast": forecast
    }

    if Path(FORECAST_LOG).exists():
        with open(FORECAST_LOG, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(entry)

    with open(FORECAST_LOG, "w") as f:
        json.dump(data, f, indent=4)

    return forecast
