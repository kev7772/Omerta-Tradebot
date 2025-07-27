import schedule
import time
import os
from trading import get_portfolio, get_profit_estimates
from sentiment_parser import get_sentiment_data
from live_logger import write_history
from telebot import TeleBot

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = TeleBot(BOT_TOKEN)

def send_autostatus():
    portfolio = get_portfolio()
    portfolio_msg = "📊 Autostatus – Portfolio:
"
    for h in portfolio:
        portfolio_msg += f"{h['coin']}: {h['amount']} → {h['value']} €\n"
    bot.send_message(ADMIN_ID, portfolio_msg)

    profits = get_profit_estimates()
    profit_msg = "💰 Buchgewinne:
"
    for p in profits:
        profit_msg += f"{p['coin']}: {p['profit']} € ({p['percent']}%)\n"
    bot.send_message(ADMIN_ID, profit_msg)

    sentiment = get_sentiment_data()
    sent_msg = f"📡 Marktstimmung: {sentiment['sentiment'].upper()} ({sentiment['score']})\n"
    sent_msg += "📚 Quellen:
" + "\n".join([f"- {s}" for s in sentiment['sources']])
    bot.send_message(ADMIN_ID, sent_msg)

def run_scheduler():
    print("⏰ Scheduler läuft dauerhaft...")
    schedule.every().day.at("00:05").do(write_history)
    schedule.every().day.at("12:00").do(send_autostatus)
    while True:
        schedule.run_pending()
        time.sleep(30)
