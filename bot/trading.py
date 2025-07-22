import os
from binance.client import Client

# API-Keys aus Environment (Railway Variables)
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

def get_portfolio():
    account = client.get_account()
    prices = client.get_all_tickers()

    holdings = []
    price_map = {p['symbol']: float(p['price']) for p in prices}

    for asset in account['balances']:
        free = float(asset['free'])
        locked = float(asset['locked'])
        total = free + locked
        if total > 0 and asset['asset'] != 'USDT':
            symbol = asset['asset'] + 'USDT'
            current_price = price_map.get(symbol, 0)
            holdings.append({
                'coin': asset['asset'],
                'amount': total,
                'price': current_price,
                'value': round(current_price * total, 2)
            })

    return holdings

def get_profit_estimates():
    data = get_portfolio()
    result = []
    for coin in data:
        # Simulierter Einstiegspreis
        buy_price = coin['price'] * 0.85
        current_value = coin['price'] * coin['amount']
        buy_value = buy_price * coin['amount']
        profit = current_value - buy_value
        result.append({
            'coin': coin['coin'],
            'profit': round(profit, 2),
            'percent': round((profit / buy_value) * 100, 2)
        })
    return result

def simulate_trade(decision, balance, portfolio, prices):
    for coin, action in decision.items():
        price = prices[coin]
        if action == "BUY" and balance > 10:
            qty = round((balance * 0.3) / price, 4)
            portfolio[coin] = portfolio.get(coin, 0) + qty
            balance -= qty * price
        elif action == "SELL" and coin in portfolio:
            balance += portfolio[coin] * price
            portfolio[coin] = 0
    return {"balance": round(balance, 2), "portfolio": portfolio}
