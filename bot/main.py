import os
import json
import threading
import telebot
from flask import Flask, request
from live_logger import write_history
from simulator import run_simulation, run_live_simulation
from logic import recommend_trades, should_trigger_panic, make_trade_decision, get_learning_log
from sentiment_parser import get_sentiment_data
from indicators import calculate_indicators
from binance.client import Client
from trading import get_portfolio, get_profit_estimates
from scheduler import run_scheduler
from decision_logger import log_trade_decisions
from feedback_loop import run_feedback_loop
from forecast import forecast_market
from visualize_learning import generate_heatmap

# === Bot Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
STATIC_URL = os.getenv("RAILWAY_STATIC_URL")
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === Webhook setzen ===
def set_telegram_webhook():
    if STATIC_URL:
        webhook_url = f"https://{STATIC_URL}/{BOT_TOKEN}"
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"ð Webhook gesetzt: {webhook_url}")
    else:
        print("â ï¸ Keine STATIC_URL gesetzt â Webhook nicht aktualisiert.")

# === Flask Webhook ===
@app.route('/')
def index():
    return 'OmertaTradeBot Webhook aktiv'

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# === Telegram Commands ===
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(message.chat.id, "👋 Willkommen beim OmertaTradeBot!")
Nutze z.â¯B. /status oder /simulate.")

@bot.message_handler(commands=['status'])
def cmd_status(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Bot lÃ¤uft â")

@bot.message_handler(commands=['enable_trading'])
def enable_trading(message):
    global ALLOW_TRADING
    if message.chat.id != ADMIN_ID:
        return
    ALLOW_TRADING = True
    bot.send_message(message.chat.id, "â Trading-Funktion aktiviert!")

@bot.message_handler(commands=['disable_trading'])
def disable_trading(message):
    global ALLOW_TRADING
    if message.chat.id != ADMIN_ID:
        return
    ALLOW_TRADING = False
    bot.send_message(message.chat.id, "ð Trading-Funktion deaktiviert!")

@bot.message_handler(commands=['portfolio'])
def cmd_portfolio(message):
    if message.chat.id != ADMIN_ID:
        return
    holdings = get_portfolio()
    text = "ð Dein Portfolio:
"
    for h in holdings:
        text += f"{h['coin']}: {h['amount']} â {h['value']} â¬
"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['profit'])
def cmd_profit(message):
    if message.chat.id != ADMIN_ID:
        return
    profits = get_profit_estimates()
    text = "ð° Buchgewinne:
"
    for p in profits:
        text += f"{p['coin']}: {p['profit']} â¬ ({p['percent']}%)
"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['panic'])
def cmd_panic(message):
    if message.chat.id != ADMIN_ID:
        return
    trigger, coin = should_trigger_panic()
    if trigger:
        bot.send_message(message.chat.id, f"â ï¸ Notbremse empfohlen bei {coin} (Ã¼ber -25%)!")
    else:
        bot.send_message(message.chat.id, "â Keine Notbremse nÃ¶tig.")

@bot.message_handler(commands=['tradelogic'])
def cmd_tradelogic(message):
    if message.chat.id != ADMIN_ID:
        return
    actions = make_trade_decision()
    text = "ð¤ Simulation:
"
    for coin, decision in actions.items():
        text += f"{coin}: {decision}
"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['loghistory'])
def cmd_loghistory(message):
    if message.chat.id != ADMIN_ID:
        return
    write_history()
    bot.send_message(message.chat.id, "ð History gespeichert.")

@bot.message_handler(commands=['simulate'])
def cmd_simulate(message):
    if message.chat.id != ADMIN_ID:
        return
    run_simulation()
    bot.send_message(message.chat.id, "ð§ª Simulation abgeschlossen.")

@bot.message_handler(commands=['livesimulate'])
def handle_livesim(message):
    if message.chat.id != ADMIN_ID:
        return
    response = run_live_simulation()
    bot.reply_to(message, response)

@bot.message_handler(commands=['recommend'])
def cmd_recommend(message):
    if message.chat.id != ADMIN_ID:
        return
    recs = recommend_trades()
    text = "ð Empfehlungen:
" + "
".join(recs)
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['sentiment'])
def cmd_sentiment(message):
    if message.chat.id != ADMIN_ID:
        return
    data = get_sentiment_data()
    text = f"ð Marktstimmung: {data['sentiment'].upper()}
"
    text += f"ð¥ Stimmungsscore: {data['score']}

"
    text += "ð¡ Quellen:
" + "
".join([f"- {s}" for s in data["sources"]])
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['indicators'])
def cmd_indicators(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        API_KEY = os.getenv("BINANCE_API_KEY")
        API_SECRET = os.getenv("BINANCE_API_SECRET")
        client = Client(API_KEY, API_SECRET)

        klines = client.get_klines(symbol='BTCUSDT', interval='1h', limit=100)
        import pandas as pd
        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df = df.astype(float)

        result = calculate_indicators(df)

        text = f"ð§  Technische Analyse BTCUSDT
"
        text += f"RSI: {result['rsi']:.2f}
"
        text += f"MACD: {result['macd']:.4f} | Signal: {result['macd_signal']:.4f}
"
        text += f"EMA20: {result['ema20']:.2f} | EMA50: {result['ema50']:.2f}
"
        text += f"Bollinger%: {result['bb_percent']:.2f}"

        bot.send_message(message.chat.id, text)
    except Exception as e:
        bot.send_message(message.chat.id, f"â Fehler bei /indicators:
{str(e)}")
