def get_all_changes_since(since_date):
    """
    Gibt Kursveränderungen aller Coins zurück seit given date.
    Rückgabe: Liste von Strings je Coin mit prozentualem Verlauf.
    """
    if not os.path.exists(HISTORY_FILE):
        return ["⚠️ Keine history.json vorhanden."]
    
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)

    today = datetime.utcnow().strftime("%Y-%m-%d")

    if since_date not in data:
        return [f"⚠️ Kein Preislog für {since_date} gefunden."]
    if today not in data:
        return [f"⚠️ Kein Preislog für heute ({today}) vorhanden."]

    old = data[since_date]
    current = data[today]

    result = []
    for coin in current:
        if coin in old:
            old_price = old[coin]
            new_price = current[coin]
            change = ((new_price - old_price) / old_price) * 100
            symbol = "📈" if change > 0 else "📉" if change < 0 else "⚖️"
            result.append(f"{coin}: {symbol} {round(change, 2)} %")

    if not result:
        return ["⚠️ Keine gemeinsamen Coins zwischen beiden Tagen."]
    
    return sorted(result)
