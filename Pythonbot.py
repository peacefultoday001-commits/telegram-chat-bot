import telebot
import json
import os
import logging
import threading
import time
from threading import Lock
from flask import Flask # NAYA

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8940270305
DATA_FILE = "bot_data.json"
DELETE_INTERVAL = 20 # 20 सेकंड

bot = telebot.TeleBot(TOKEN)
db_lock = Lock()

app = Flask(__name__) # NAYA

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def empty_db():
    return {"history": {}, "reply_map": {}, "blocked": [], "autodelete": {}}

def load_data():
    with db_lock:
        if not os.path.exists(DATA_FILE): return empty_db()
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            data.setdefault("history", {}); data.setdefault("reply_map", {}); data.setdefault("blocked", []); data.setdefault("autodelete", {})
            for uid in data["history"]:
                data["history"][uid].setdefault("name", "Unknown")
                data["history"][uid].setdefault("username", "N/A")
            return data
        except Exception as e: logging.error(f"DB Read: {e}"); return empty_db()

def save_data(data):
    with db_lock:
        temp = DATA_FILE + ".tmp"
        try:
            with open(temp, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp, DATA_FILE)
        except Exception as e: logging.error(f"DB Save: {e}")

def ensure_user(data, user_id):
    user_id = str(user_id)
    if user_id not in data["history"]: data["history"][user_id] = {"u": [], "a": [], "name": "Unknown", "username": "N/A"}
    if user_id not in data["autodelete"]: data["autodelete"][user_id] = False

def add_history(data, user_id, user_message_id=None, admin_message_id=None, name="Unknown", username="N/A"):
    user_id = str(user_id); ensure_user(data, user_id)
    data["history"][user_id]["name"] = name
    data["history"][user_id]["username"] = username
    if user_message_id is not None: data["history"][user_id]["u"].append(int(user_message_id))
    if admin_message_id is not None: data["history"][user_id]["a"].append(int(admin_message_id))

# ====== AUTO DELETE WORKER 20s ======
def auto_delete_worker():
    while True:
        time.sleep(DELETE_INTERVAL)
        data = load_data()
        for user_id, status in list(data["autodelete"].items()):
            if status == True:
                history = data["history"].get(user_id, {})
                deleted_any = False
                for msg_id in history.get("u", [])[:]:
                    try: bot.delete_message(int(user_id), int(msg_id)); deleted_any = True
                    except: pass
                for msg_id in history.get("a", [])[:]:
                    try: bot.delete_message(ADMIN_ID, int(msg_id)); deleted_any = True
                    except: pass
                if deleted_any:
                    data["history"][user_id]["u"] = []
                    data["history"][user_id]["a"] = []
                    save_data(data)
# =================================

@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id; data = load_data()
    if chat_id == ADMIN_ID:
        bot.send_message(ADMIN_ID, f"🛡️ PRIVATE ADMIN PANEL\n↩️ Reply करके जवाब दें।\n\n👥 /users\n📨 /msg\n🚫 /blocked\n⛔ /ban <id>\n✅ /unban <id>\n🔥 /autodeleteon\n❌ /autodeleteoff\n🧹 /clear\n💥 /clearall\n\n⏱️ AutoDelete Timer: {DELETE_INTERVAL}s")
    else:
        user_id = str(chat_id)
        if user_id in data["blocked"]:
            bot.send_message(chat_id, "⛔ आपको इस bot से block कर दिया गया है।")
            return
        name = message.from_user.first_name or "No Name"
        username = f"@{message.from_user.username}" if message.from_user.username else "N/A"
        is_returning = user_id in data["history"]
        ensure_user(data, chat_id)
        data["history"][user_id]["name"] = name
        data["history"][user_id]["username"] = username
        status = "✅ ON" if data["autodelete"].get(user_id) else "❌ OFF"

        if is_returning:
            bot.send_message(chat_id, f"🙏 वापस स्वागत है!\n\nAuto Delete Status: {status}\nTimer: {DELETE_INTERVAL}s\n/use /autodeleteon या /autodeleteoff")
            admin_msg = bot.send_message(ADMIN_ID, f"🔄 USER RETURNED\n👤 {name}\n🆔 `{chat_id}`\nAutoDelete: {status}", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"🙏 नमस्ते!\n\nAuto Delete Status: {status}\nTimer: {DELETE_INTERVAL}s\n`/autodeleteon` या `/autodeleteoff`", parse_mode="Markdown")
            admin_msg = bot.send_message(ADMIN_ID, f"🔔 NEW USER\n👤 {name}\n🆔 `{chat_id}`\nAutoDelete: {status}", parse_mode="Markdown")

        data["reply_map"][str(admin_msg.message_id)] = str(chat_id)
        save_data(data)

#... tera saara code yahi rahega...

# ====== Render ke liye FLASK ROUTE ======
@app.route('/')
def home():
    return "Bot is Alive"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

if __name__ == "__main__":
    threading.Thread(target=auto_delete_worker, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start() # NAYA
    print(f"Bot Started ✅ with Auto Delete {DELETE_INTERVAL}s")
    bot.infinity_polling(skip_pending=True, allowed_updates=["message", "message_reaction"])