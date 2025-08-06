# === OmertaTradeBot: main.py ===
import os
import json
import threading
import telebot
from flask import Flask, request
from scheduler import run_scheduler
from decision_logger import log_trade_decisions
from simulator import run_simulation
from logic import make_trade_decision
from feedback_loop import run_feedback_loop

# === Setup ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === JSON-Dateien sicherstellen ===
def ensure_json_file(filename, default_data):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump(default_data, f)
        print(f"🆕 {filename} automatisch erstellt.")

json_files = {
    "history.json": [],
    "ghost_log.json": [],
    "ghost_positions.json": [],
    "simulation_log.json": [],
    "learning_log.json": {},
    "crawler_data.json": []
}
for file, content in json_files.items():
    ensure_json_file(file, content)

# === Webhook ===
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

# === Startup-Aktionen ===
def startup_tasks():
    print("📈 Starte Initial-Simulation...")
    run_simulation()
    print("🤖 Logge Entscheidungen...")
    decisions = make_trade_decision()
    log_trade_decisions(decisions)
    print("🧠 Starte Feedback-Learning...")
    run_feedback_loop()

# === Befehlshandler registrieren ===
from commands.status_commands import register_status_commands
# Weitere Imports folgen später (jede Datei einzeln reinladen)

register_status_commands(bot, ADMIN_ID)
# Weitere Registrierungen folgen später

# === Bot starten ===
if __name__ == '__main__':
    threading.Thread(target=run_scheduler).start()
    threading.Thread(target=startup_tasks).start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
