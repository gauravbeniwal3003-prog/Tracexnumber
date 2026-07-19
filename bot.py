"""
TraceX Lookup Bot - Premium Telecom & OSINT Lookup Bot
Version: 7.0.0 - Enhanced Broadcast, Multi-Channel Gatekeeper & Pretty Printing
"""

import os
import sys
import time
import re
import uuid
import json
import threading
import signal
from datetime import datetime, timedelta, timezone
import requests
from flask import Flask, request, jsonify
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8525568503:AAHjydzj4bXdjVcS9c5jiL3CghFDfBePXXw"
ADMIN_ID = 7850023357
ADMIN_CHANNEL_ID = -1003743686626
ADMIN_USERNAME = r"@gaurav\_beni\_0001"
BOT_VERSION = "7.0.0"

# Target Gatekeeper Channels
REQUIRED_CHANNELS = [
    {"username": "@beniwalmods", "link": "https://t.me/beniwalmods"},
    {"username": "@Gaurav_beni_0001", "link": "https://t.me/Gaurav_beni_0001"},
    {"username": "@BeniwalzonYT", "link": "https://t.me/BeniwalzonYT"},
    {"username": "@gauravbeniwalchat", "link": "https://t.me/gauravbeniwalchat"}
]

# Costs Setup
CREDIT_COSTS = {
    "number": 2,
    "email": 20,
    "vehicle": 5,
    "telegram": 5,
    "veh_owner_num": 10,
    "identity": 5,
    "pancard": 5,
    "ifsc": 3
}

# Updated Plan Configuration ($1 = 1 Credit)
PLAN_CONFIG = {
    "c49": {"amount": 49, "credits": 49, "unlimited_minutes": 0, "payment_for": "credits", "label": "49 Credits"},
    "c99": {"amount": 99, "credits": 99, "unlimited_minutes": 0, "payment_for": "credits", "label": "99 Credits"},
    "c499": {"amount": 499, "credits": 499, "unlimited_minutes": 0, "payment_for": "credits", "label": "499 Credits"},
    "c1499": {"amount": 1499, "credits": 1499, "unlimited_minutes": 0, "payment_for": "credits", "label": "1499 Credits"},
    "u1h": {"amount": 49, "credits": 0, "unlimited_minutes": 60, "payment_for": "unlimited", "label": "1 Hour Unlimited"},
    "u1d": {"amount": 99, "credits": 0, "unlimited_minutes": 1440, "payment_for": "unlimited", "label": "1 Day Unlimited"},
    "u1w": {"amount": 499, "credits": 0, "unlimited_minutes": 10080, "payment_for": "unlimited", "label": "7 Days Unlimited"},
    "u1m": {"amount": 1499, "credits": 0, "unlimited_minutes": 43200, "payment_for": "unlimited", "label": "30 Days Unlimited"},
    "protect_number": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_number", "label": "Number Protection"},
    "protect_telegram": {"amount": 99, "credits": 0, "unlimited_minutes": 0, "payment_for": "protect_telegram", "label": "Telegram ID Protection"}
}

COOLDOWN_SECONDS = 3
PAYMENT_QR_IMAGE = os.getenv("PAYMENT_QR_IMAGE", "payment_qr.png")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://tracexnumber.web.app")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing vital variables in environment setup.")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, threaded=True)

# Supabase Client Core
class _SupabaseResult:
    def __init__(self, data=None):
        self.data = data if data is not None else []

class _SupabaseLiteClient:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    def table(self, name):
        return _SupabaseTableQuery(self, name)

class _SupabaseTableQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.params = {}
    def select(self, columns="*"):
        self.method = "GET"; self.params["select"] = columns; return self
    def insert(self, payload):
        self.method = "POST"; self.payload = payload; return self
    def update(self, payload):
        self.method = "PATCH"; self.payload = payload; return self
    def eq(self, column, value):
        self.params[str(column)] = "eq." + str(value); return self
    def limit(self, n):
        self.params["limit"] = str(int(n)); return self
    def execute(self):
        url = f"{self.client.url}/rest/v1/{self.table}"
        headers = dict(self.client.headers)
        if self.method in ["POST", "PATCH"]:
            headers["Prefer"] = "return=representation"
        res = requests.request(self.method, url, params=self.params, json=getattr(self, 'payload', None), headers=headers, timeout=25)
        return _SupabaseResult(res.json() if res.text else [])

supabase = _SupabaseLiteClient(SUPABASE_URL, SUPABASE_KEY)

# App States & Session Locks
user_states = {}
user_cooldown = {}
temp_data = {}
active_sessions = set()
sessions_lock = threading.Lock()
proof_forwarded_txs = set()
MAINTENANCE_MODE = False

# ==================== KEYBOARDS ====================
def get_main_keyboard(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📱 NUMBER LOOKUP"), KeyboardButton("💬 TELEGRAM LOOKUP"))
    kb.add(KeyboardButton("🆔 IDENTITY CARD LOOKUP"), KeyboardButton("🏦 IFSC LOOKUP"))
    kb.add(KeyboardButton("💳 PAN CARD LOOKUP"), KeyboardButton("📧 EMAIL LOOKUP"))
    kb.add(KeyboardButton("🚗 VEHICLE LOOKUP"), KeyboardButton("👤 VEHICLE TO OWNER"))
    kb.add(KeyboardButton("💎 MY STATUS"), KeyboardButton("🛒 ADD CREDITS"))
    kb.add(KeyboardButton("🛡️ PRIVACY SHIELD"), KeyboardButton("📢 HELP & SUPPORT"))
    if user_id == ADMIN_ID:
        kb.add(KeyboardButton("🛠️ SYSTEM ADMIN PANEL"))
    return kb

def get_inline_cancel():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ CANCEL OPERATION", callback_data="cancel_action"))
    return markup

# ==================== GATEKEEPER ENGINE ====================
def check_user_channels_status(user_id):
    if user_id == ADMIN_ID:
        return []
    left_groups = []
    for ch in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(ch["username"], user_id)
            if member.status not in ["member", "administrator", "creator"]:
                left_groups.append(ch)
        except Exception:
            left_groups.append(ch)
    return left_groups

def enforce_gatekeeper(message):
    user_id = message.from_user.id
    left_channels = check_user_channels_status(user_id)
    if left_channels:
        markup = InlineKeyboardMarkup(row_width=1)
        for ch in left_channels:
            markup.add(InlineKeyboardButton(f"✨ JOIN {ch['username'].upper()}", url=ch["link"]))
        markup.add(InlineKeyboardButton("🔄 VERIFY MY MEMBERSHIPS", callback_data="verify_channels"))
        
        bot.send_message(
            message.chat.id,
            "🔒 *ACCESS RESTRICTED!*\n\nTo continue using TraceX Premium Lookup systems, you must be a member of our community channels. Please join the missing networks listed below:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return False
    return True

# ==================== API HANDLERS ====================
def clean_and_print_response(raw_text):
    try:
        parsed = json.loads(raw_text)
        return f"```json\n{json.dumps(parsed, indent=2)}\n```"
    except Exception:
        return f"```text\n{raw_text.strip()}\n```"

def call_lookup_api(url):
    try:
        res = requests.get(url, headers={"User-Agent": "TraceX/7.0"}, timeout=30)
        if res.status_code == 200:
            return res.text, None
        return None, f"HTTP_{res.status_code}"
    except Exception as e:
        return None, str(e)

# ==================== USER PROFILE METHODS ====================
def get_user(user_id):
    try:
        res = supabase.table("telegram_users").select("*").eq("telegram_user_id", user_id).execute()
        if res.data:
            return res.data[0]
        new_user = {
            "telegram_user_id": user_id, "credits": 10, "total_searches": 0,
            "first_seen": datetime.now(timezone.utc).isoformat(), "is_banned": False
        }
        ins = supabase.table("telegram_users").insert(new_user).execute()
        return ins.data[0] if ins.data else new_user
    except Exception:
        return {"telegram_user_id": user_id, "credits": 0, "total_searches": 0, "is_banned": False}

def check_unlimited(user):
    expiry = user.get("unlimited_expiry")
    if expiry:
        try:
            dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            if dt > datetime.now(timezone.utc):
                return True, expiry
        except Exception:
            pass
    return False, None

def deduct_user_credits(user_id, amount):
    user = get_user(user_id)
    is_unl, _ = check_unlimited(user)
    if is_unl:
        return True
    current = int(user.get("credits", 0))
    if current >= amount:
        supabase.table("telegram_users").update({"credits": current - amount}).eq("telegram_user_id", user_id).execute()
        return True
    return False

# ==================== CENTRAL DISPATCH ROUTER ====================
def execute_search_flow(message, feature_key, api_url_template, search_query):
    user_id = message.from_user.id
    cost = CREDIT_COSTS[feature_key]
    
    user = get_user(user_id)
    is_unl, unl_exp = check_unlimited(user)
    
    if int(user.get("credits", 0)) < cost and not is_unl:
        bot.send_message(message.chat.id, f"❌ *Insufficient Balance!* This specialized search requires `{cost}` credits.", parse_mode="Markdown")
        return

    session_id = f"{user_id}_{feature_key}"
    with sessions_lock:
        if session_id in active_sessions:
            bot.send_message(message.chat.id, "⏳ An active lookup cycle is currently running. Please hold on.", parse_mode="Markdown")
            return
        active_sessions.add(session_id)

    load_msg = bot.send_message(message.chat.id, "⚡ *Querying secure databanks... Please wait*", parse_mode="Markdown")
    raw_res, error = call_lookup_api(api_url_template.format(search_query))
    
    with sessions_lock:
        active_sessions.discard(session_id)

    if error or not raw_res:
        bot.edit_message_text("❌ *Database Connection Error.* No balance was deducted.", message.chat.id, load_msg.message_id, parse_mode="Markdown")
        return

    if not deduct_user_credits(user_id, cost):
        bot.edit_message_text("❌ Transaction Processing Error.", message.chat.id, load_msg.message_id)
        return

    # Update total lookups counter
    try:
        supabase.table("telegram_users").update({"total_searches": int(user.get("total_searches", 0)) + 1}).eq("telegram_user_id", user_id).execute()
    except Exception:
        pass

    pretty_data = clean_and_print_response(raw_res)
    updated_user = get_user(user_id)
    
    header = f"🔍 *TRACEX INTEL REPORT*\n⚡ *Target:* `{search_query}`\n\n"
    footer = f"\n\n💰 *Deduction:* `{cost} Credits` | *Remaining:* `{updated_user.get('credits', 0)}`"
    if is_unl:
        footer = f"\n\n🚀 *Plan Info:* Unlimited Active (Expires: {unl_exp[:16]})"
        
    final_text = header + pretty_data + footer
    
    if len(final_text) > 4000:
        bot.delete_message(message.chat.id, load_msg.message_id)
        bot.send_message(message.chat.id, header + "🔽 Big data payload forwarded below:", parse_mode="Markdown")
        bot.send_message(message.chat.id, pretty_data, parse_mode="Markdown")
        bot.send_message(message.chat.id, footer, parse_mode="Markdown")
    else:
        bot.edit_message_text(final_text, message.chat.id, load_msg.message_id, parse_mode="Markdown")

# ==================== INPUT STAGE PROCESSORS ====================
def ask_input(message, state_name, text_prompt):
    if not enforce_gatekeeper(message):
        return
    user_states[message.from_user.id] = state_name
    bot.send_message(message.chat.id, text_prompt, reply_markup=get_inline_cancel(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def main_router(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user.get("is_banned"):
        bot.reply_to(message, "🚫 Access Denied. Your account signature is currently flagged.")
        return

    text = message.text

    # Handle active text injection state routes
    if user_states.get(user_id):
        current_state = user_states[user_id]
        del user_states[user_id]
        
        if text == "❌ CANCEL OPERATION" or text.startswith("/"):
            bot.send_message(message.chat.id, "🔄 Current operation dropped.", reply_markup=get_main_keyboard(user_id))
            return
            
        if current_state == "st_num":
            clean = re.sub(r"\D", "", text)
            execute_search_flow(message, "number", "https://tracexdata-api.onrender.com/api/lookup?key=Pvttbott&number={}", clean)
        elif current_state == "st_tg":
            execute_search_flow(message, "telegram", "https://tracexdata-api.onrender.com/api/telegram?key=Pvtbott&api={}", text.replace("@", ""))
        elif current_state == "st_id":
            execute_search_flow(message, "identity", "https://exploitsindia.site//osint-api/aadhar.php?exploits={}", text)
        elif current_state == "st_ifsc":
            execute_search_flow(message, "ifsc", "https://exploitsindia.site//osint-api/ifsc.php?exploits={}", text.upper())
        elif current_state == "st_pan":
            execute_search_flow(message, "pancard", "https://tracexdata-api.onrender.com/api/pancard?key=Pvtbot&query={}", text.upper())
        elif current_state == "st_veh":
            execute_search_flow(message, "vehicle", "https://tracexdata-api.onrender.com/api/vehicle?key=Pvtbotttt&query={}", text.upper())
        elif current_state == "st_vown":
            execute_search_flow(message, "veh_owner_num", "https://tracexdata-api.onrender.com/api/veh-owner-num?key=Pvtbottt&query={}", text.upper())
        elif current_state == "st_email":
            execute_search_flow(message, "email", "https://tracexdata-api.onrender.com/api/email?key=Pvttbot&query={}", text)
        elif current_state == "st_proof":
            bot.send_message(message.chat.id, "⚠️ Invalid submission format. Please forward a verification screenshot image.")
        return

    # Standard App Menus Routing
    if text == "/start":
        bot.send_message(message.chat.id, f"🔥 *Welcome to TraceX Premium OSINT Intel Hub v{BOT_VERSION}*\n\nSelect a dynamic engine function below to run deep queries.", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
    elif text == "📱 NUMBER LOOKUP":
        ask_input(message, "st_num", "📱 *Enter Indian Target Number:*")
    elif text == "💬 TELEGRAM LOOKUP":
        ask_input(message, "st_tg", "💬 *Enter Target Telegram Username:*")
    elif text == "🆔 IDENTITY CARD LOOKUP":
        ask_input(message, "st_id", "🆔 *Enter target National Identity Card Number:*")
    elif text == "🏦 IFSC LOOKUP":
        ask_input(message, "st_ifsc", "🏦 *Enter Target Bank Branch IFSC Code:*")
    elif text == "💳 PAN CARD LOOKUP":
        ask_input(message, "st_pan", "💳 *Enter Target PAN Card String ID:*")
    elif text == "📧 EMAIL LOOKUP":
        ask_input(message, "st_email", "📧 *Enter Target Email Address:*")
    elif text == "🚗 VEHICLE LOOKUP":
        ask_input(message, "st_veh", "🚗 *Enter target Vehicle Plate Number:*")
    elif text == "👤 VEHICLE TO OWNER":
        ask_input(message, "st_vown", "👤 *Enter target Vehicle Plate Number for Phone extraction:*")
    
    elif text == "💎 MY STATUS":
        is_unl, exp = check_unlimited(user)
        status_text = f"👤 *USER MASTER INDEX CARD*\n━━━━━━━━━━━━━━━━━━\n✨ *User Key:* `{user_id}`\n💎 *Credits Balance:* `{user.get('credits', 0)}` Units\n📊 *Total Search Audits:* `{user.get('total_searches', 0)}` Lookups\n"
        if is_unl:
            status_text += f"🚀 *Unlimited Plan:* Enabled until `{exp[:16]}`"
        bot.send_message(message.chat.id, status_text, parse_mode="Markdown")
        
    elif text == "🛒 ADD CREDITS":
        show_credit_store(message)
    elif text == "🛠️ SYSTEM ADMIN PANEL" and user_id == ADMIN_ID:
        show_admin_panel(message)
    elif text == "📢 HELP & SUPPORT":
        bot.send_message(message.chat.id, f"🛠️ *TraceX Operations Desk*\n\nFor premium system support, reach out to the core admin network directly at: {ADMIN_USERNAME}", parse_mode="Markdown")

# ==================== PHOTO MANAGEMENT ENGINE ====================
@bot.message_handler(content_types=['photo', 'document'])
def file_ingestion_pipeline(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    if not (isinstance(state, dict) and state.get("state") == "awaiting_screenshot"):
        return

    tx_code = state.get("tx_code")
    del user_states[user_id]

    if tx_code in proof_forwarded_txs:
        bot.reply_to(message, "✅ This payment confirmation key is already processing inside the verify logs.")
        return
    proof_forwarded_txs.add(tx_code)

    caption = f"📸 *INCOMING PAYMENT SCREENSHOT AUDIT*\n━━━━━━━━━━━━━━━━━━━━━\n👤 *User Identifier:* `{user_id}`\n🧾 *Transaction Hash:* `{tx_code}`\n\nApproval operations:\n`/adminverify {tx_code}`\n`/adminreject {tx_code}`"
    
    # Direct Forward Pipeline
    try:
        bot.send_message(ADMIN_CHANNEL_ID, caption, parse_mode="Markdown")
        bot.copy_message(ADMIN_CHANNEL_ID, message.chat.id, message.message_id)
        
        # Parallel direct admin message synchronization
        bot.send_message(ADMIN_ID, f"📢 *Direct Sync Alert:* New proof file received for hash `{tx_code}`", parse_mode="Markdown")
        bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
        
        bot.reply_to(message, "✨ *Screenshot successfully logged!* Our admin team has received the record. Verification will process manually.", reply_markup=get_main_keyboard(user_id), parse_mode="Markdown")
    except Exception as e:
        proof_forwarded_txs.discard(tx_code)
        bot.reply_to(message, f"❌ Pipeline transmission fail. Contact administration manually: {ADMIN_USERNAME}")

# ==================== TRANSACTION ENGINE ====================
def show_credit_store(message):
    markup = InlineKeyboardMarkup(row_width=2)
    for k, v in PLAN_CONFIG.items():
        markup.add(InlineKeyboardButton(f"💳 {v['label']} - ₹{v['amount']}", callback_data=f"buy_{k}"))
    bot.send_message(message.chat.id, "🛒 *TraceX Premium Store Matrix*\n\nSelect a balance plan pack package signature below:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def inline_callback_router(call):
    user_id = call.from_user.id
    
    if call.data == "verify_channels":
        left = check_user_channels_status(user_id)
        if not left:
            bot.answer_callback_query(call.id, "Verification Success! ✅", show_alert=True)
            bot.edit_message_text("🎉 All membership signatures verified! Enjoy using TraceX Premium Lookup.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, f"❌ You are still missing {len(left)} networks.", show_alert=True)
            
    elif call.data == "cancel_action":
        user_states.pop(user_id, None)
        bot.edit_message_text("🔄 Current action dropped by client request.", call.message.chat.id, call.message.message_id)
        
    elif call.data.startswith("buy_"):
        plan_key = call.data.replace("buy_", "")
        plan = PLAN_CONFIG.get(plan_key)
        tx_code = "TXH" + uuid.uuid4().hex[:12].upper()
        
        user_states[user_id] = {"state": "awaiting_screenshot", "tx_code": tx_code}
        
        caption = f"🧾 *TraceX Invoice Matrix:* `{tx_code}`\n💰 *Amount Due:* ₹{plan['amount']}\n📦 *Plan Selection:* `{plan['label']}`\n\n📌 *Scan the QR code below and pay exactly the total stated amount. Once complete, upload your payment confirmation file right here.*"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ ABORT ORDER", callback_data="cancel_action"))
        
        if os.path.exists(PAYMENT_QR_IMAGE):
            with open(PAYMENT_QR_IMAGE, "rb") as qr:
                bot.send_photo(call.message.chat.id, qr, caption=caption, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(call.message.chat.id, caption + "\n\n⚠️ QR code image file missing on core host server.", reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

# ==================== ASYNC ADMIN PIPELINES ====================
def show_admin_panel(message):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📢 EXECUTE GLOBAL SYSTEM BROADCAST", callback_data="adm_bcast"),
        InlineKeyboardButton("❌ CLOSE WORKSTATION", callback_data="cancel_action")
    )
    bot.send_message(message.chat.id, "🛠️ *TraceX Admin Control Matrix*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "adm_bcast")
def admin_broadcast_init(call):
    if call.from_user.id != ADMIN_ID: return
    user_states[ADMIN_ID] = "awaiting_bcast_payload"
    bot.edit_message_text("📢 *Input your broadcast message payload:*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

def async_broadcast_runner(text_payload, all_users):
    success = 0
    failed = 0
    for uid in all_users:
        try:
            bot.send_message(uid, f"📢 *GLOBAL SYSTEM NOTIFICATION*\n━━━━━━━━━━━━━━━━━━━━\n\n{text_payload}", parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1
        time.sleep(0.04) # Smooth processing block to safely stay inside global threshold constraints
        
    try:
        bot.send_message(ADMIN_ID, f"📊 *BROADCAST REPORT CONCLUDED*\n━━━━━━━━━━━━━━━━━━━━━\n✅ *Delivered Successfully:* `{success}` users\n❌ *Transmission drops:* `{failed}` profiles", parse_mode="Markdown")
    except Exception:
        pass

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "awaiting_bcast_payload")
def process_admin_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    del user_states[ADMIN_ID]
    
    payload = message.text
    bot.send_message(ADMIN_ID, "🚀 *Asynchronous broadcast process successfully initiated in background core loop...* Tracking logs will return upon completion.", parse_mode="Markdown")
    
    try:
        res = supabase.table("telegram_users").select("telegram_user_id").execute()
        users_list = [int(row["telegram_user_id"]) for row in res.data] if res.data else []
    except Exception:
        users_list = []
        
    if not users_list:
        bot.send_message(ADMIN_ID, "❌ Target user index returns empty.")
        return
        
    threading.Thread(target=async_broadcast_runner, args=(payload, users_list), daemon=True).start()

# ==================== FLASK SERVER CONTEXT ====================
app = Flask(__name__)
@app.route('/')
def health(): return "TraceX Core Platform Online"

def init_keep_alive():
    def loop():
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), use_reloader=False)
    t = threading.Thread(target=loop)
    t.daemon = True
    t.start()

# ==================== PROCESS INITIATION ====================
if __name__ == "__main__":
    init_keep_alive()
    print("🚀 TraceX Premium System Operations Running...")
    
    def shutdown_signal(sig, frame):
        print("\n🛑 Execution processes dropped cleanly via system termination command.")
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown_signal)

    while True:
        try:
            bot.infinity_polling(timeout=50, skip_pending=True)
        except Exception as e:
            print(f"Polling warning caught: {e}")
            time.sleep(5)