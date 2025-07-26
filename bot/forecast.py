import random

def forecast_market():
    """
    Simuliert eine einfache Marktprognose auf Basis von Zufall (Demo-Zweck)
    Rückgabe: bullish | neutral | bearish
    """
    forecast = random.choices(
        ["bullish", "neutral", "bearish"],
        weights=[0.4, 0.3, 0.3],  # leicht bullischer Bias
        k=1
    )[0]
    print(f"📊 Prognose für Marktstimmung: {forecast}")
    return forecast
