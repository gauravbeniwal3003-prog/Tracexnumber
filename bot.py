"""
TraceX Lookup Bot - Premium Telecom Lookup Bot
Enhanced Credit System - Daily Free Credits & Giveaways
"""

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import requests
import time
import re
from datetime import datetime, timedelta
import os
import threading
import signal
import sys
import random
import os

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = -1003743686626
ADMIN_CHANNEL_ID = -1003743686626  # Channel for logs

API_URL = "https://vishalnumberimfoapi.vk177384.workers.dev/"
API_KEY = "TVB_Y9T032"

FREE_CREDITS_ON_START = 3  # Permanent credits on start
DAILY_FREE_CREDIT = 0  # Free daily credit
COOLDOWN_SECONDS = 3
AUTO_DELETE_SECONDS = 120
ADMIN_USERNAME = "@gaurav\\_beniwal\\_0001"
BOT_VERSION = "3.1"

CREDIT_PACKS = {
    10: 5,
    30: 20,
    50: 50,
    100: 150
}

QR_CODE_PATH = "qrcode.png"

bot = telebot.TeleBot(BOT_TOKEN)

user_states = {}
user_cooldown = {}
pending_payments = {}
temp_data = {}
daily_credit_check_running = False

# ==================== MAINTENANCE MODE ====================

MAINTENANCE_MODE = False

MAINTENANCE_MESSAGE = """
⚠️ BOT UNDER MAINTENANCE
🛠️ TraceX is currently under maintenance and upgrades.
⏰ Please try again later.
📢 Till then, join our official channel for updates and announcements: https://t.me/Gaurav_beni_0001
🙏 Thanks for your patience.
"""

@bot.message_handler(func=lambda message: MAINTENANCE_MODE and message.from_user.id != 7850023357)
def maintenance_handler(message):
    bot.reply_to(message, MAINTENANCE_MESSAGE, parse_mode='Markdown')
    return

@bot.callback_query_handler(func=lambda call: MAINTENANCE_MODE and call.from_user.id != 7850023357)
def maintenance_callback(call):
    bot.answer_callback_query(
        call.id,
        "Bot under maintenance 🛠️",
        show_alert=True
    )
    return

MAINTENANCE_MODE = False

# ==================== UNIVERSAL BUTTON SYSTEM ====================
GROUP_LINK = "https://t.me/Gaurav_beni_0001"

def universal_markup(back=False, buy=False, join=False, admin=False):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []

    if buy:
        buttons.append(InlineKeyboardButton("💎 BUY CREDITS", callback_data="buy"))
    if join:
        buttons.append(InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK))
    if admin:
        buttons.append(InlineKeyboardButton("👨‍💻 CONTACT ADMIN", url="https://t.me/gaurav_beniwal_0001"))
    if back:
        buttons.append(InlineKeyboardButton("🏠 MAIN MENU", callback_data="main_menu"))

    for btn in buttons:
        markup.add(btn)
    return markup

# ==================== UI DESIGN SYSTEM ====================
def footer():
    return f"\n\n━━━━━━━━━━━━━━━━\n👨‍💻 Admin: {ADMIN_USERNAME}\n👥 Group: [Join Community]({GROUP_LINK})"

def header(title, emoji="🚀"):
    return f"{emoji} *{title}*\n━━━━━━━━━━━━━━━━\n"

def success_box(text):
    return f"✅ {text}"

def error_box(text):
    return f"❌ {text}"

def info_box(text):
    return f"ℹ️ {text}"

def warning_box(text):
    return f"⚠️ {text}"

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    
    # Check if old table exists and migrate
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    table_exists = c.fetchone()
    
    if table_exists:
        # Check if old columns exist
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'credits' in columns and 'permanent_credits' not in columns:
            print("🔄 Migrating old database to new schema...")
            # Add new columns
            c.execute("ALTER TABLE users ADD COLUMN permanent_credits INTEGER DEFAULT 0")
            c.execute("ALTER TABLE users ADD COLUMN daily_credits INTEGER DEFAULT 0")
            c.execute("ALTER TABLE users ADD COLUMN last_daily_credit_date TEXT")
            # Migrate old credits to permanent_credits
            c.execute("UPDATE users SET permanent_credits = credits")
            print("✅ Database migration completed!")
    
    # Create or update tables
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, 
                  permanent_credits INTEGER DEFAULT 0,
                  daily_credits INTEGER DEFAULT 0,
                  last_daily_credit_date TEXT,
                  total_searches INTEGER DEFAULT 0, 
                  is_banned INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS lookup_cache 
                 (phone_number TEXT PRIMARY KEY, 
                  result TEXT, 
                  timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY, 
                  user_id INTEGER, 
                  amount INTEGER, 
                  credits INTEGER, 
                  utr TEXT, 
                  screenshot_id TEXT,
                  status TEXT, 
                  timestamp TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS search_history 
                 (id INTEGER PRIMARY KEY, 
                  user_id INTEGER, 
                  number TEXT, 
                  result_summary TEXT,
                  timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS giveaway_log 
                 (id INTEGER PRIMARY KEY, 
                  admin_id INTEGER,
                  credits INTEGER,
                  total_users INTEGER,
                  timestamp TEXT)''')
    
    conn.commit()
    conn.close()
    print("✅ Database ready")

def get_user(user_id):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        # Create new user
        c.execute("INSERT INTO users (user_id, permanent_credits, daily_credits, last_daily_credit_date, total_searches, is_banned) VALUES (?, ?, ?, ?, ?, ?)", 
                  (user_id, FREE_CREDITS_ON_START, 0, None, 0, 0))
        conn.commit()
        conn.close()
        return {'user_id': user_id, 'permanent_credits': FREE_CREDITS_ON_START, 
                'daily_credits': 0, 'last_daily_credit_date': None,
                'total_searches': 0, 'is_banned': 0}
    
    # Handle both old and new schema
    if len(user) == 3:  # Old schema (user_id, credits, total_searches, is_banned might be missing)
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        
        if 'is_banned' in columns:
            c.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
            is_banned = c.fetchone()[0]
        else:
            is_banned = 0
            c.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        
        conn.close()
        return {'user_id': user[0], 'permanent_credits': user[1], 
                'daily_credits': 0, 'last_daily_credit_date': None,
                'total_searches': user[2] if len(user) > 2 else 0, 'is_banned': is_banned}
    
    conn.close()
    return {'user_id': user[0], 'permanent_credits': user[1], 'daily_credits': user[2],
            'last_daily_credit_date': user[3], 'total_searches': user[4], 'is_banned': user[5]}

def get_total_credits(user_id):
    user = get_user(user_id)
    return user['permanent_credits'] + user['daily_credits']

def add_permanent_credits(user_id, amount):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("UPDATE users SET permanent_credits = permanent_credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()
    return get_total_credits(user_id)

def add_daily_credits(user_id, amount):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("UPDATE users SET daily_credits = daily_credits + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()
    return get_total_credits(user_id)

def deduct_credit(user_id):
    user = get_user(user_id)
    
    # First use daily credits
    if user['daily_credits'] > 0:
        conn = sqlite3.connect('tracex.db')
        c = conn.cursor()
        c.execute("UPDATE users SET daily_credits = daily_credits - 1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True
    # Then use permanent credits
    elif user['permanent_credits'] > 0:
        conn = sqlite3.connect('tracex.db')
        c = conn.cursor()
        c.execute("UPDATE users SET permanent_credits = permanent_credits - 1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

def add_daily_free_credit():
    """Add daily free credit to all users who haven't received today's credit"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    
    # Get all users who haven't received daily credit today
    c.execute("SELECT user_id FROM users WHERE last_daily_credit_date != ? OR last_daily_credit_date IS NULL", (today,))
    users = c.fetchall()
    
    success_count = 0
    for user in users:
        user_id = user[0]
        try:
            c.execute("UPDATE users SET daily_credits = daily_credits + ?, last_daily_credit_date = ? WHERE user_id=?", 
                      (DAILY_FREE_CREDIT, today, user_id))
            success_count += 1
            
            # Send daily credit message to user
            try:
                user_data = get_user(user_id)
                msg = f"""
🎁 *DAILY FREE CREDIT!*

✨ `{DAILY_FREE_CREDIT}` free credit added to your account!

💎 *Your Credits:*
━━━━━━━━━━━━━━━━
🔹 Daily Credits: `{DAILY_FREE_CREDIT}`
🔹 Permanent Credits: `{user_data['permanent_credits']}`

📊 *Total Credits:* `{get_total_credits(user_id)}`

💡 Daily credits expire at midnight!
Use them before they're gone!

━━━━━━━━━━━━━━━━
{footer()}
"""
                bot.send_message(user_id, msg, parse_mode='Markdown')
            except:
                pass
        except Exception as e:
            print(f"Error giving daily credit to {user_id}: {e}")
    
    conn.commit()
    conn.close()
    
    if success_count > 0:
        log_msg = f"""
🎁 *DAILY CREDIT DISTRIBUTED*

✅ Users: `{success_count}`
💎 Credits each: `{DAILY_FREE_CREDIT}`
📅 Date: `{today}`

Daily free credits have been added to all active users.
"""
        try:
            bot.send_message(ADMIN_ID, log_msg, parse_mode='Markdown')
        except:
            pass
    
    return success_count

def check_and_give_daily_credits():
    """Background thread to check and give daily credits at midnight"""
    global daily_credit_check_running
    
    if daily_credit_check_running:
        return
    
    daily_credit_check_running = True
    
    def daily_credit_worker():
        while True:
            now = datetime.now()
            # Calculate next midnight (12:00 AM)
            next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
            seconds_until_midnight = (next_midnight - now).total_seconds()
            
            # Wait until midnight
            if seconds_until_midnight > 0:
                time.sleep(seconds_until_midnight)
            
            # Give daily credits
            add_daily_free_credit()
            
            # Wait a bit before next check
            time.sleep(60)
    
    thread = threading.Thread(target=daily_credit_worker, daemon=True)
    thread.start()

def giveaway_credits_to_all(credits, admin_id):
    """Giveaway credits to all users"""
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    
    # Get all non-banned users
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    
    success_count = 0
    failed_count = 0
    
    for user in users:
        user_id = user[0]
        try:
            add_permanent_credits(user_id, credits)
            success_count += 1
            
            # Send message to user
            msg = f"""
🎉 *GIVEAWAY TIME!* 🎉

✨ `{credits}` FREE PERMANENT CREDITS added to your account!

💎 *Your Credits Updated:*
━━━━━━━━━━━━━━━━
🔹 Permanent Credits: Increased by `{credits}`
📊 *Total Credits:* `{get_total_credits(user_id)}`

🎊 Thanks for being part of TraceX Family!

━━━━━━━━━━━━━━━━
{footer()}
"""
            bot.send_message(user_id, msg, parse_mode='Markdown')
        except Exception as e:
            failed_count += 1
            print(f"Failed to send giveaway to {user_id}: {e}")
        
        time.sleep(0.05)  # Small delay to avoid flooding
    
    # Log the giveaway
    c.execute("INSERT INTO giveaway_log (admin_id, credits, total_users, timestamp) VALUES (?, ?, ?, ?)",
              (admin_id, credits, success_count, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return success_count, failed_count

def add_to_history(user_id, number, result_summary=""):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("INSERT INTO search_history (user_id, number, result_summary) VALUES (?, ?, ?)", 
              (user_id, number, result_summary[:200]))
    conn.commit()
    conn.close()

def get_history(user_id, limit=5):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("SELECT number, timestamp, result_summary FROM search_history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", 
              (user_id, limit))
    history = c.fetchall()
    conn.close()
    return history

def lookup_number(phone):
    try:
        url = f"{API_URL}?number={phone}"
        r = requests.get(url, timeout=10)
        return r.json()
    except Exception as e:
        print(f"API Error: {e}")
        return None

def get_stats():
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(total_searches) FROM users")
    total_searches = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(permanent_credits) FROM users")
    total_permanent = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(daily_credits) FROM users")
    total_daily = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned=1")
    banned_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM transactions WHERE status='pending'")
    pending_payments_count = c.fetchone()[0]
    
    c.execute("SELECT SUM(amount) FROM transactions WHERE status='completed'")
    total_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM lookup_cache")
    cache_size = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE last_daily_credit_date = ?", (datetime.now().strftime('%Y-%m-%d'),))
    daily_received = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_searches': total_searches,
        'total_permanent': total_permanent,
        'total_daily': total_daily,
        'banned_users': banned_users,
        'pending_payments': pending_payments_count,
        'total_revenue': total_revenue,
        'cache_size': cache_size,
        'daily_received': daily_received
    }

def ban_user(user_id):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

# ==================== UI COMPONENTS ====================
message_context = None

def main_menu_markup():
    global message_context
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📱 NUMBER LOOKUP", callback_data="lookup"),
        InlineKeyboardButton("💎 MY CREDITS", callback_data="credits")
    )
    markup.add(
        InlineKeyboardButton("🛒 BUY CREDITS", callback_data="buy"),
        InlineKeyboardButton("📜 HISTORY", callback_data="history")
    )
    markup.add(
        InlineKeyboardButton("👤 PROFILE", callback_data="profile"),
        InlineKeyboardButton("ℹ️ HELP", callback_data="help")
    )
    if message_context and hasattr(message_context, 'from_user') and message_context.from_user.id == 7850023357:
        markup.add(InlineKeyboardButton("🛠 ADMIN", callback_data="admin"))
    return markup

def cancel_button():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("❌ CANCEL", callback_data="cancel"))
    return markup

# ==================== BOT HANDLERS ====================
@bot.message_handler(commands=['start'])
def start(message):
    global message_context
    message_context = message
    
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if user['is_banned']:
        bot.reply_to(message, f"🚫 YOU ARE BANNED\n\nContact: {ADMIN_USERNAME}")
        return
    
    total_credits = get_total_credits(user_id)
    
    welcome_msg = f"""
{header("TRACEX LOOKUP", "🚀")}

👋 Welcome, *{message.from_user.first_name}*

💎 *Credit Details:*
━━━━━━━━━━━━━━━━
🔹 Permanent: `{user['permanent_credits']}`
🔹 Daily: `{user['daily_credits']}`
📊 Total: `{total_credits}`

🔎 Total Searches: `{user['total_searches']}`

━━━━━━━━━━━━━━━━
🎯 *FEATURES*
• Instant Number Lookup
• Fast Response
• Secure Credits System
• Search History
• Premium Database

━━━━━━━━━━━━━━━━
🎁 New users get `{FREE_CREDITS_ON_START}` permanent credits!
🎁 Daily free credit at 12:00 AM!

👇 Choose an option below
{footer()}
"""
    
    bot.send_message(message.chat.id, welcome_msg, reply_markup=main_menu_markup(), parse_mode='Markdown')

@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    bot.reply_to(message, "❌ Cancelled. Use /start for main menu.", 
                reply_markup=main_menu_markup(), parse_mode='Markdown')

@bot.message_handler(commands=['verify'])
def verify_command(message):
    if message.from_user.id != 7850023357:
        return
    
    try:
        parts = message.text.split()

        if len(parts) != 2:
            bot.reply_to(
                message,
                "❌ Usage: `/verify transaction_id`",
                parse_mode='Markdown'
            )
            return
        
        trans_id = int(parts[1])
        
        conn = sqlite3.connect('tracex.db')
        c = conn.cursor()

        c.execute(
            "SELECT * FROM transactions WHERE id=?",
            (trans_id,)
        )

        trans = c.fetchone()
        
        if not trans:
            bot.reply_to(
                message,
                "❌ Transaction not found!",
                parse_mode='Markdown'
            )
            conn.close()
            return
        
        if trans[6] in ["completed", "rejected"]:
            bot.reply_to(
                message,
                f"⚠️ Transaction already {trans[6]}!",
                parse_mode='Markdown'
            )
            conn.close()
            return
        
        target_user = trans[1]
        credits = trans[3]

        new_total = add_permanent_credits(target_user, credits)
        
        c.execute(
            "UPDATE transactions SET status='completed' WHERE id=?",
            (trans_id,)
        )

        conn.commit()
        conn.close()
        
        bot.reply_to(
            message,
            f"""
✅ *PAYMENT VERIFIED!*

👤 *User:* `{target_user}`
💎 *Permanent Credits Added:* `{credits}`
📊 *New Total:* `{new_total}`

✅ Transaction #{trans_id} completed
            """,
            parse_mode='Markdown'
        )
        
        try:
            bot.send_message(
                target_user,
                f"""
✅ *PAYMENT VERIFIED!*

💎 `{credits}` permanent credits added to your account!
📊 *New Total:* `{new_total}`

Use /start to continue!
                """,
                parse_mode='Markdown'
            )
        except:
            pass
        
        bot.send_message(
            ADMIN_ID,
            f"""
✅ *Transaction #{trans_id} verified!*

💎 {credits} permanent credits added to user `{target_user}`
            """,
            parse_mode='Markdown'
        )
            
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error: {e}",
            parse_mode='Markdown'
        )


@bot.message_handler(commands=['reject'])
def reject_command(message):
    if message.from_user.id != 7850023357:
        return
    
    try:
        parts = message.text.split()

        if len(parts) != 2:
            bot.reply_to(
                message,
                "❌ Usage: `/reject transaction_id`",
                parse_mode='Markdown'
            )
            return
        
        trans_id = int(parts[1])
        
        conn = sqlite3.connect('tracex.db')
        c = conn.cursor()

        c.execute(
            "SELECT * FROM transactions WHERE id=?",
            (trans_id,)
        )

        trans = c.fetchone()
        
        if not trans:
            bot.reply_to(
                message,
                "❌ Transaction not found!",
                parse_mode='Markdown'
            )
            conn.close()
            return
        
        if trans[6] in ["completed", "rejected"]:
            bot.reply_to(
                message,
                f"⚠️ Transaction already {trans[6]}!",
                parse_mode='Markdown'
            )
            conn.close()
            return
        
        target_user = trans[1]
        
        c.execute(
            "UPDATE transactions SET status='rejected' WHERE id=?",
            (trans_id,)
        )

        conn.commit()
        conn.close()
        
        bot.reply_to(
            message,
            f"""
❌ *PAYMENT REJECTED!*

👤 *User:* `{target_user}`

❌ Transaction #{trans_id} rejected
            """,
            parse_mode='Markdown'
        )
        
        try:
            bot.send_message(
                target_user,
                f"""
❌ *PAYMENT REJECTED!*

Your payment screenshot was rejected.

📞 Contact admin if you think this is a mistake.
                """,
                parse_mode='Markdown'
            )
        except:
            pass
        
        bot.send_message(
            ADMIN_ID,
            f"❌ *Transaction #{trans_id} rejected!*",
            parse_mode='Markdown'
        )
            
    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Error: {e}",
            parse_mode='Markdown'
        )
@bot.message_handler(commands=['maintenance'])
def toggle_maintenance(message):
    global MAINTENANCE_MODE
    

    if message.from_user.id != 7850023357:
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.reply_to(
            message,
            "Usage:\n/maintenance on\n/maintenance off"
        )
        return

    mode = parts[1].lower()

    if mode == "on":
        MAINTENANCE_MODE = True
        bot.reply_to(
            message,
            "🛠 Maintenance mode ENABLED"
        )

    elif mode == "off":
        MAINTENANCE_MODE = False
        bot.reply_to(
            message,
            "✅ Maintenance mode DISABLED"
        )

    else:
        bot.reply_to(
            message,
            "Invalid option!\nUse:\n/maintenance on\n/maintenance off"
        )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    global message_context
    global MAINTENANCE_MODE
    
    message_context = call.message
    
    user_id = call.from_user.id
    user = get_user(user_id)
    
    if user['is_banned']:
        bot.answer_callback_query(call.id, "You are banned!", show_alert=True)
        return
    
    if call.data == "main_menu":
        bot.edit_message_text(
            "🏠 *MAIN MENU*",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu_markup(),
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "cancel":
        if user_id in user_states:
            del user_states[user_id]
        if user_id in temp_data:
            del temp_data[user_id]
        bot.edit_message_text(
            "❌ Cancelled. Use /start for main menu.",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=main_menu_markup(),
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "lookup":
        user_states[user_id] = "awaiting_number"
        msg = bot.send_message(
            call.message.chat.id,
            "📱 *Enter 10-digit number:*\n\n`Example: 9876543210`\n\nType /cancel to abort",
            reply_markup=cancel_button(),
            parse_mode='Markdown'
        )
        bot.register_next_step_handler(msg, process_lookup)
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "credits":
        total_credits = get_total_credits(user_id)
        credits_msg = f"""
*💎 MY CREDITS*

━━━━━━━━━━━━━━━━━━
🔹 *Permanent Credits:* `{user['permanent_credits']}`
🔸 *Daily Credits:* `{user['daily_credits']}`
📊 *Total Credits:* `{total_credits}`
🔎 *Used:* `{user['total_searches']}`
━━━━━━━━━━━━━━━━━━

*📦 CREDIT PACKS*
• Rs.10 = 5 permanent credits
• Rs.30 = 20 permanent credits
• Rs.50 = 50 permanent credits
• Rs.100 = 150 permanent credits

*🎁 FREE DAILY CREDIT*
Get {DAILY_FREE_CREDIT} free credit every day at 12:00 AM!
Daily credits expire at midnight if unused!
        """
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🛒 BUY PERMANENT CREDITS", callback_data="buy"))
        markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.edit_message_text(credits_msg, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "buy":
        show_credit_packs(call.message)
        bot.answer_callback_query(call.id)
        return
    
    elif call.data.startswith("pack_"):
        handle_pack_selection(call)
        return
    
    elif call.data == "history":
        history = get_history(user_id)
        if not history:
            history_msg = "📜 *No search history yet!*"
        else:
            history_msg = "*📜 SEARCH HISTORY*\n\n"
            for i, (number, timestamp, summary) in enumerate(history, 1):
                history_msg += f"{i}. `{number}`\n   🕐 {timestamp[:16]}\n\n"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 BACK", callback_data="main_menu"))
        bot.edit_message_text(history_msg, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "profile":
        total_credits = get_total_credits(user_id)
        profile_msg = f"""
👤 *USER PROFILE*
━━━━━━━━━━━━━━━━━━

🆔 User ID
`{user_id}`

👤 Name
`{call.from_user.first_name}`

💎 *Credit Details*
━━━━━━━━━━━━━━━━━━
🔹 Permanent: `{user['permanent_credits']}`
🔸 Daily: `{user['daily_credits']}`
📊 Total: `{total_credits}`

🔎 Total Searches
`{user['total_searches']}`

🛡️ Account Status
`{'ACTIVE ✅' if not user['is_banned'] else 'BANNED ❌'}`

━━━━━━━━━━━━━━━━━━
🚀 Thanks for using TraceX
{footer()}
"""
        markup = universal_markup(back=True, join=True, admin=True)
        bot.edit_message_text(profile_msg, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "help":
        help_msg = f"""
📖 *HOW TO USE TRACEX*
━━━━━━━━━━━━━━━━━━

1️⃣ Click NUMBER LOOKUP
2️⃣ Enter mobile number
3️⃣ Get instant results

━━━━━━━━━━━━━━━━━━
💎 *CREDIT SYSTEM*

• New User: `{FREE_CREDITS_ON_START}` permanent credits
• Daily Free: `{DAILY_FREE_CREDIT}` credit at 12:00 AM
• Daily credits expire at midnight
• Purchased credits never expire
• Daily credits used first

━━━━━━━━━━━━━━━━━━
🛒 BUYING PERMANENT CREDITS

• Select credit pack
• Make payment
• Send screenshot
• Admin verifies payment

━━━━━━━━━━━━━━━━━━
⚡ FEATURES

✅ Fast Lookup
✅ Search History
✅ Secure Payments
✅ Auto Delete System

{footer()}
"""
        markup = universal_markup(back=True, join=True, admin=True)
        bot.edit_message_text(help_msg, call.message.chat.id, call.message.message_id,
                            reply_markup=markup, parse_mode='Markdown')
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "admin":
        if call.from_user.id != 7850023357:
            bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
            return
        show_admin_panel(call.message)
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "broadcast_confirm":
        if call.from_user.id != 7850023357:
            return
        confirm_broadcast(call)
        return
    
    elif call.data == "giveaway_confirm":
        if call.from_user.id != 7850023357:
            return
        confirm_giveaway(call)
        return
    
    elif call.data in ["admin_add", "admin_remove", "admin_ban", "admin_unban", "admin_broadcast", "admin_stats", "admin_transactions", "admin_back", "admin_giveaway", "maintenance_on", "maintenance_off"]:
        if call.from_user.id != 7850023357:
            return
        
        if call.data == "admin_add":
            user_states[user_id] = "admin_add"
            msg = bot.send_message(call.message.chat.id, "➕ *ADD PERMANENT CREDITS*\n\nFormat: `user_id credits`\nExample: `123456789 50`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_add)
        elif call.data == "admin_remove":
            user_states[user_id] = "admin_remove"
            msg = bot.send_message(call.message.chat.id, "➖ *REMOVE CREDITS*\n\nFormat: `user_id credits`\nExample: `123456789 10`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_remove)
        elif call.data == "admin_ban":
            user_states[user_id] = "admin_ban"
            msg = bot.send_message(call.message.chat.id, "🚫 *BAN USER*\n\nEnter user ID to ban\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_ban)
        elif call.data == "admin_unban":
            user_states[user_id] = "admin_unban"
            msg = bot.send_message(call.message.chat.id, "✅ *UNBAN USER*\n\nEnter user ID to unban\nExample: `123456789`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_unban)
        elif call.data == "admin_broadcast":
            user_states[user_id] = "admin_broadcast"
            msg = bot.send_message(call.message.chat.id, "📢 *BROADCAST*\n\nSend your broadcast message below:\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_broadcast)
        elif call.data == "admin_giveaway":
            user_states[user_id] = "admin_giveaway"
            msg = bot.send_message(call.message.chat.id, "🎁 *GIVEAWAY CREDITS*\n\nEnter number of permanent credits to give to ALL users:\n\nExample: `50`\n\nType /cancel to abort", reply_markup=cancel_button(), parse_mode='Markdown')
            bot.register_next_step_handler(msg, process_admin_giveaway)
        elif call.data == "admin_stats":
            show_admin_stats(call.message)
        elif call.data == "admin_transactions":
            show_admin_transactions(call.message)
        elif call.data == "admin_back":
            show_admin_panel(call.message)
        elif call.data == "maintenance_on":
            MAINTENANCE_MODE = True
            bot.answer_callback_query(call.id, "🛠 Maintenance Enabled", show_alert=True)

        elif call.data == "maintenance_off":
            MAINTENANCE_MODE = False
            bot.answer_callback_query(call.id, "✅ Maintenance Disabled", show_alert=True)    
        
        bot.answer_callback_query(call.id)
        return

# ==================== CREDIT PACKS ====================
def show_credit_packs(message):
    packs_msg = f"""
💎 *PREMIUM CREDIT STORE*
━━━━━━━━━━━━━━━━━━

🎯 Rs.10  →  5 Permanent Credits
⚡ Rs.30  →  20 Permanent Credits
🚀 Rs.50  →  50 Permanent Credits
👑 Rs.100 → 150 Permanent Credits

━━━━━━━━━━━━━━━━━━
✅ Permanent Credits NEVER EXPIRE
✅ Instant Activation
✅ Fast Verification
✅ Secure Payments

👇 Select your pack below
{footer()}
"""
    
    markup = InlineKeyboardMarkup(row_width=2)
    for price, credits in CREDIT_PACKS.items():
        btn_text = f"Rs.{price} - {credits} permanent credits"
        callback = f"pack_{price}_{credits}"
        markup.add(InlineKeyboardButton(btn_text, callback_data=callback))
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="credits"))
    
    bot.send_message(message.chat.id, packs_msg, reply_markup=markup, parse_mode='Markdown')

def handle_pack_selection(call):
    parts = call.data.split("_")
    price = int(parts[1])
    credits = int(parts[2])
    user_id = call.from_user.id
    
    pending_payments[user_id] = {'price': price, 'credits': credits, 'timestamp': time.time()}
    
    if os.path.exists(QR_CODE_PATH):
        with open(QR_CODE_PATH, 'rb') as qr_file:
            payment_msg = f"""
💳 *PAYMENT INSTRUCTIONS*
━━━━━━━━━━━━━━━━━━

💰 Amount: `Rs.{price}`
💎 Permanent Credits: `{credits}`

📌 STEPS:
1️⃣ Scan QR Code
2️⃣ Pay exact amount
3️⃣ Send screenshot or UTR
4️⃣ Wait for verification

━━━━━━━━━━━━━━━━━━
⚡ Verification usually takes 1-5 mins
{footer()}
"""
            bot.send_photo(call.message.chat.id, qr_file, caption=payment_msg, parse_mode='Markdown')
    else:
        payment_msg = f"""
*💳 PAYMENT INFO*

*Amount:* Rs.{price}
*Permanent Credits:* {credits}

Type /cancel to abort
"""
        markup = universal_markup(join=True, admin=True)
        bot.send_message(call.message.chat.id, payment_msg, reply_markup=markup, parse_mode='Markdown')
    
    bot.answer_callback_query(call.id, f"Pay Rs.{price} and send screenshot/UTR")

# Handle screenshot
@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user_id = message.from_user.id
    
    if user_id not in pending_payments:
        bot.reply_to(message, "❌ No pending payment found.\n\nUse /start to select a credit pack.", parse_mode='Markdown')
        return
    
    payment = pending_payments[user_id]
    
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("""INSERT INTO transactions 
                 (user_id, amount, credits, screenshot_id, status, timestamp) 
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (user_id, payment['price'], payment['credits'], 
               message.photo[-1].file_id, "pending", datetime.now().isoformat()))
    conn.commit()
    trans_id = c.lastrowid
    conn.close()
    
    admin_msg = f"""
*💰 NEW PAYMENT RECEIVED*

👤 *User:* {message.from_user.first_name}
🆔 *User ID:* `{user_id}`
@ *Username:* @{message.from_user.username if message.from_user.username else 'Not set'}

📦 *Order Details:*
💵 *Amount:* Rs.{payment['price']}
💎 *Permanent Credits:* {payment['credits']}

🔧 *Verify Command:* `/verify {trans_id}`

📅 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    try:
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_msg, parse_mode='Markdown')
        
        try:
            bot.send_message(7850023357, f"📸 New payment screenshot posted in channel!\n\nUser: {message.from_user.first_name}\nAmount: Rs.{payment['price']}\nTransaction ID: #{trans_id}", parse_mode='Markdown')
        except:
            pass
        
        bot.reply_to(message, f"""
✅ *PAYMENT SUBMITTED!*

💰 *Amount:* Rs.{payment['price']}
💎 *Permanent Credits:* {payment['credits']}

⏳ *Status:* Pending Verification

Admin will verify your payment shortly.
        """, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Failed to send to channel: {e}")
        bot.reply_to(message, f"""
⚠️ *Payment received but there was an issue.*

📞 *Contact Admin directly:* {ADMIN_USERNAME}

Transaction ID: #{trans_id}
Amount: Rs.{payment['price']}
        """, parse_mode='Markdown')
    
    del pending_payments[user_id]

# ==================== LOOKUP PROCESS ====================
def process_lookup(message):
    user_id = message.from_user.id
    phone = message.text.strip()
    
    if user_id in user_states:
        del user_states[user_id]
    
    if phone == "/cancel":
        bot.reply_to(message, "❌ Cancelled!", reply_markup=main_menu_markup(), parse_mode='Markdown')
        return
    
    if not re.match(r'^[6-9]\d{9}$', phone):
        bot.reply_to(message, "❌ *Invalid number!*\n\nEnter 10-digit Indian number.\nExample: `9876543210`", 
                    reply_markup=main_menu_markup(), parse_mode='Markdown')
        return
    
    if user_id in user_cooldown:
        if time.time() - user_cooldown[user_id] < COOLDOWN_SECONDS:
            wait_time = int(COOLDOWN_SECONDS - (time.time() - user_cooldown[user_id]))
            bot.reply_to(message, f"⏳ *Please wait {wait_time} seconds*", reply_markup=main_menu_markup(), parse_mode='Markdown')
            return
    
    user = get_user(user_id)
    total_credits = get_total_credits(user_id)
    
    if total_credits <= 0:
        markup = universal_markup(buy=True, join=True, admin=True)
        bot.reply_to(message, "❌ *No credits!* Buy more credits or wait for daily free credit.", reply_markup=markup, parse_mode='Markdown')
        return
    
    user_cooldown[user_id] = time.time()
    loading_msg = bot.reply_to(message, "🔍 *Searching...*", parse_mode='Markdown')
    
    time.sleep(1)
    bot.edit_message_text("🔍 *Searching..*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    time.sleep(1)
    bot.edit_message_text("🔍 *Searching...*", message.chat.id, loading_msg.message_id, parse_mode='Markdown')
    
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("SELECT result FROM lookup_cache WHERE phone_number=?", (phone,))
    cached = c.fetchone()
    conn.close()
    
    if cached:
        bot.edit_message_text(f"⚡ *Cached Result*\n\n{cached[0]}", 
                            message.chat.id, loading_msg.message_id, parse_mode='Markdown')
        add_to_history(user_id, phone, "Cached")
        
        # Send search log to admin channel
        log_message = f"""
🔍 *SEARCH LOG*
━━━━━━━━━━━━━━━━
👤 User: {message.from_user.first_name}
🆔 ID: `{user_id}`
📱 Number: `{phone}`
📊 Result: Cached
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            bot.send_message(ADMIN_CHANNEL_ID, log_message, parse_mode='Markdown')
        except:
            pass
        return
    
    result = lookup_number(phone)

    if result and result.get('results'):

        deduct_success = deduct_credit(user_id)

        if not deduct_success:
            bot.edit_message_text("❌ *Failed to deduct credit. Please try again.*", 
                                message.chat.id, loading_msg.message_id, parse_mode='Markdown')
            return

        conn = sqlite3.connect('tracex.db')
        c = conn.cursor()
        c.execute(
            "UPDATE users SET total_searches=total_searches+1 WHERE user_id=?",
            (user_id,)
        )
        conn.commit()
        conn.close()

        # ==================== FIXED PARSING LOGIC ====================
        # Get the results from API response
        api_results = result.get('results', {})
        
        # Parse results properly to handle both dict and list formats
        parsed_results = []
        
        if isinstance(api_results, dict):
            # If it's a dictionary with numbered keys like "Result 1", "Result 2", etc.
            if api_results:
                # Check if it's a nested dict with result entries
                for key, value in api_results.items():
                    if isinstance(value, dict):
                        # Each result is a dict with fields
                        parsed_results.append(value)
                    elif isinstance(value, list):
                        # Extend if it's a list
                        parsed_results.extend(value)
                    else:
                        # Single value - create a dict with it
                        parsed_results.append({'data': value})
            # Also handle case where results is already a list but wrapped in dict
            elif isinstance(api_results, list):
                parsed_results = api_results
            else:
                parsed_results = []
        elif isinstance(api_results, list):
            # If it's already a list, use it directly
            parsed_results = api_results
        else:
            # If results is None or other type
            parsed_results = []
        
        # If still empty, try to get direct data from result
        if not parsed_results:
            # Try to extract data from result dict directly
            if 'name' in result or 'mobile' in result:
                parsed_results = [result]
        
        updated_user = get_user(user_id)
        updated_total = get_total_credits(user_id)
        
        output = f"""
🔍 *NUMBER LOOKUP RESULT*
━━━━━━━━━━━━━━━━━━

📊 Total Results Found: `{len(parsed_results)}`
"""

        # Store first result for history
        first_name = "Unknown"
        
        for idx, data in enumerate(parsed_results, 1):
            # Get values with proper handling for missing keys
            # Support both lowercase and camelCase field names
            name = data.get('name') or data.get('Name') or data.get('full_name') or 'N/A'
            if idx == 1 and name != 'N/A':
                first_name = name
                
            alt_mobile = data.get('alt_mobile') or data.get('alternate_mobile') or data.get('Alt_Mobile') or 'N/A'
            if alt_mobile == 'NA' or alt_mobile == 'n/a':
                alt_mobile = 'N/A'
            
            father_name = data.get('father_name') or data.get('Father_Name') or data.get('father') or 'N/A'
            email = data.get('email') or data.get('Email') or 'N/A'
            if email == 'n/a':
                email = 'N/A'
                
            aadhar = data.get('aadhar_number') or data.get('aadhar') or data.get('Aadhar') or 'N/A'
            if aadhar == 'n/a':
                aadhar = 'N/A'
                
            operator = data.get('operator') or data.get('Operator') or data.get('carrier') or 'N/A'
            circle = data.get('state_circle') or data.get('circle') or data.get('Circle') or data.get('state') or 'N/A'
            address = data.get('address') or data.get('Address') or data.get('full_address') or 'N/A'
            if address == 'NA':
                address = 'N/A'
            
            # Get mobile number from either key
            mobile = data.get('mobile') or data.get('Mobile') or data.get('phone') or phone
            
            output += f"""

━━━━━━━━━━━━━━━━━━
📄 *RESULT {idx}*

📱 Mobile: `{mobile}`
📞 Alternate: `{alt_mobile}`
👤 Name: `{name}`
👨 Father: `{father_name}`
📧 Email: `{email}`
🪪 Aadhaar: `{aadhar}`
📡 Operator: `{operator}`
📍 Circle: `{circle}`
🏠 Address: `{address}`"""

        output += f"""

━━━━━━━━━━━━━━━━━━
💎 *Credits Used:* `1`
💎 *Credits Left:* `{updated_total}`
🔎 *Total Searches:* `{updated_user['total_searches']}`

⚠️ Auto delete in {AUTO_DELETE_SECONDS} sec
{footer()}
"""

        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔍 NEW SEARCH", callback_data="lookup"),
            InlineKeyboardButton("🏠 MENU", callback_data="main_menu")
        )
        markup.add(
            InlineKeyboardButton("📢 JOIN GROUP", url=GROUP_LINK)
        )

        sent_msg = bot.edit_message_text(
            output,
            message.chat.id,
            loading_msg.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )

        conn = sqlite3.connect('tracex.db')
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO lookup_cache (phone_number, result) VALUES (?, ?)",
            (phone, output[:500])
        )
        conn.commit()
        conn.close()

        add_to_history(user_id, phone, first_name)

        # Send search log to admin channel
        log_message = f"""
🔍 *SEARCH LOG*
━━━━━━━━━━━━━━━━
👤 User: {message.from_user.first_name}
🆔 ID: `{user_id}`
📱 Number: `{phone}`
👤 Name Found: `{first_name}`
📊 Records: `{len(parsed_results)}`
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            bot.send_message(ADMIN_CHANNEL_ID, log_message, parse_mode='Markdown')
        except:
            pass

        def auto_delete():
            time.sleep(AUTO_DELETE_SECONDS)
            try:
                bot.delete_message(message.chat.id, sent_msg.message_id)
            except:
                pass

        threading.Thread(target=auto_delete, daemon=True).start()

    else:
        output = f"""
❌ *NO DATA FOUND*
━━━━━━━━━━━━━━━━━━

📱 Number
`{phone}`

🚫 No records available in database

💡 Tips:
• Check number again
• Try another number
• Ensure Indian mobile number

━━━━━━━━━━━━━━━━━━
💎 Credits NOT deducted
{footer()}
"""

        bot.edit_message_text(
            output,
            message.chat.id,
            loading_msg.message_id,
            parse_mode='Markdown'
        )
        add_to_history(user_id, phone, "No data")
        
        # Send search log to admin channel
        log_message = f"""
🔍 *SEARCH LOG*
━━━━━━━━━━━━━━━━
👤 User: {message.from_user.first_name}
🆔 ID: `{user_id}`
📱 Number: `{phone}`
📊 Result: No Data Found
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        try:
            bot.send_message(ADMIN_CHANNEL_ID, log_message, parse_mode='Markdown')
        except:
            pass

# ==================== ADMIN FUNCTIONS ====================
def show_admin_panel(message):
    stats = get_stats()
    
    admin_msg = f"""
*🛠 ADMIN PANEL*

*📊 STATS*
👥 Users: `{stats['total_users']}`
🔍 Searches: `{stats['total_searches']}`
💾 Cache: `{stats['cache_size']}`

*💎 CREDITS SYSTEM*
💎 Permanent: `{stats['total_permanent']}`
⭐ Daily: `{stats['total_daily']}`
🎁 Daily Received Today: `{stats['daily_received']}`

*💰 FINANCIAL*
💵 Revenue: Rs.{stats['total_revenue']}
⏳ Pending: `{stats['pending_payments']}`
🚫 Banned: `{stats['banned_users']}`

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ ADD CREDITS", callback_data="admin_add"),
        InlineKeyboardButton("➖ REMOVE CREDITS", callback_data="admin_remove")
    )
    markup.add(
        InlineKeyboardButton("🚫 BAN USER", callback_data="admin_ban"),
        InlineKeyboardButton("✅ UNBAN USER", callback_data="admin_unban")
    )
    markup.add(
        InlineKeyboardButton("📢 BROADCAST", callback_data="admin_broadcast"),
        InlineKeyboardButton("🎁 GIVEAWAY", callback_data="admin_giveaway")
    )
    markup.add(
        InlineKeyboardButton("📊 STATS", callback_data="admin_stats"),
        InlineKeyboardButton("📋 TRANSACTIONS", callback_data="admin_transactions")
    )
    markup.add(
    InlineKeyboardButton("🛠 MAINTENANCE ON", callback_data="maintenance_on"),
    InlineKeyboardButton("✅ MAINTENANCE OFF", callback_data="maintenance_off")
    )
    markup.add(
        InlineKeyboardButton("🔙 BACK", callback_data="main_menu")
    )
    
    bot.send_message(message.chat.id, admin_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_stats(message):
    stats = get_stats()
    
    stats_msg = f"""
*📊 DETAILED STATS*

━━━━━━━━━━━━━━━━━━
👥 *USERS*
━━━━━━━━━━━━━━━━━━
Total Users: `{stats['total_users']}`
Banned Users: `{stats['banned_users']}`
Active Users: `{stats['total_users'] - stats['banned_users']}`

━━━━━━━━━━━━━━━━━━
💎 *CREDITS*
━━━━━━━━━━━━━━━━━━
Total Permanent: `{stats['total_permanent']}`
Total Daily: `{stats['total_daily']}`
Total Credits: `{stats['total_permanent'] + stats['total_daily']}`
Daily Received Today: `{stats['daily_received']}`

━━━━━━━━━━━━━━━━━━
📊 *USAGE*
━━━━━━━━━━━━━━━━━━
Total Searches: `{stats['total_searches']}`
Cache Size: `{stats['cache_size']}`

━━━━━━━━━━━━━━━━━━
💰 *FINANCIAL*
━━━━━━━━━━━━━━━━━━
Total Revenue: Rs.{stats['total_revenue']}
Pending Payments: `{stats['pending_payments']}`

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    
    bot.send_message(message.chat.id, stats_msg, reply_markup=markup, parse_mode='Markdown')

def show_admin_transactions(message):
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("SELECT id, user_id, amount, credits, status, timestamp FROM transactions ORDER BY timestamp DESC LIMIT 20")
    transactions = c.fetchall()
    conn.close()
    
    if not transactions:
        trans_msg = "📋 *No transactions found!*"
    else:
        trans_msg = "*📋 RECENT TRANSACTIONS*\n\n"
        for trans in transactions:
            status_emoji = "✅" if trans[4] == "completed" else "⏳"
            trans_msg += f"{status_emoji} *#{trans[0]}* | User: `{trans[1]}` | Rs.{trans[2]} | {trans[3]} credits\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 BACK", callback_data="admin_back"))
    
    bot.send_message(message.chat.id, trans_msg, reply_markup=markup, parse_mode='Markdown')

def process_admin_add(message):
    user_id = message.from_user.id
    if user_id != 7850023357:
        return
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup())
        return
    
    try:
        parts = message.text.split()
        target_user = int(parts[0])
        credits = int(parts[1])
        new_total = add_permanent_credits(target_user, credits)
        
        bot.reply_to(message, f"✅ Added {credits} permanent credits to `{target_user}`\nNew total: `{new_total}`", parse_mode='Markdown')
        
        try:
            bot.send_message(target_user, f"✅ *{credits} permanent credits added!*\nNew total: `{new_total}`", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid format! Use: `user_id credits`", parse_mode='Markdown')

def process_admin_remove(message):
    user_id = message.from_user.id
    if user_id != 7850023357:
        return
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup())
        return
    
    try:
        parts = message.text.split()
        target_user = int(parts[0])
        credits = int(parts[1])
        user = get_user(target_user)
        
        # Remove from permanent credits first
        if user['permanent_credits'] >= credits:
            new_permanent = user['permanent_credits'] - credits
            conn = sqlite3.connect('tracex.db')
            c = conn.cursor()
            c.execute("UPDATE users SET permanent_credits=? WHERE user_id=?", (new_permanent, target_user))
            conn.commit()
            conn.close()
            new_total = get_total_credits(target_user)
            bot.reply_to(message, f"✅ Removed {credits} credits from `{target_user}`\nNew total: `{new_total}`", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ User only has {user['permanent_credits']} permanent credits!", parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid format! Use: `user_id credits`", parse_mode='Markdown')

def process_admin_ban(message):
    user_id = message.from_user.id
    if user_id != 7850023357:
        return
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup())
        return
    
    try:
        target_user = int(message.text.strip())
        ban_user(target_user)
        bot.reply_to(message, f"✅ Banned user `{target_user}`", parse_mode='Markdown')
        
        try:
            bot.send_message(target_user, "🚫 *You have been banned.* Contact support.", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!", parse_mode='Markdown')

def process_admin_unban(message):
    user_id = message.from_user.id
    if user_id != 7850023357:
        return
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup())
        return
    
    try:
        target_user = int(message.text.strip())
        unban_user(target_user)
        bot.reply_to(message, f"✅ Unbanned user `{target_user}`", parse_mode='Markdown')
        
        try:
            bot.send_message(target_user, "✅ *You have been unbanned!* Use /start", parse_mode='Markdown')
        except:
            pass
    except:
        bot.reply_to(message, "❌ Invalid user ID!", parse_mode='Markdown')

def process_admin_broadcast(message):
    user_id = message.from_user.id
    if user_id != 7850023357:
        return
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup())
        return
    
    broadcast_text = message.text.strip()
    
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ YES, SEND", callback_data="broadcast_confirm"),
        InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel")
    )
    
    temp_data[user_id] = {'broadcast_text': broadcast_text}
    
    bot.reply_to(message, f"📢 *Confirm Broadcast*\n\n📝 Message:\n`{broadcast_text}`\n\nSend to all active users?", 
                reply_markup=markup, parse_mode='Markdown')

def process_admin_giveaway(message):
    user_id = message.from_user.id
    if user_id != 7850023357:
        return
    
    if user_id in user_states:
        del user_states[user_id]
    
    if message.text == "/cancel":
        bot.reply_to(message, "Cancelled", reply_markup=main_menu_markup())
        return
    
    try:
        credits = int(message.text.strip())
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ YES, GIVE AWAY", callback_data="giveaway_confirm"),
            InlineKeyboardButton("❌ NO, CANCEL", callback_data="cancel")
        )
        
        temp_data[user_id] = {'giveaway_credits': credits}
        
        bot.reply_to(message, f"🎁 *Confirm Giveaway*\n\nGive `{credits}` permanent credits to ALL active users?\n\nThis will be sent to all users immediately!", 
                    reply_markup=markup, parse_mode='Markdown')
    except:
        bot.reply_to(message, "❌ Invalid number! Enter a valid credit amount.", parse_mode='Markdown')

def confirm_broadcast(call):
    user_id = call.from_user.id
    if user_id != 7850023357:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    if user_id not in temp_data:
        bot.edit_message_text("❌ Broadcast cancelled. No data found.", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=main_menu_markup())
        return
    
    broadcast_text = temp_data[user_id]['broadcast_text']
    
    conn = sqlite3.connect('tracex.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned=0")
    users = c.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    # Edit the confirmation message to show progress
    bot.edit_message_text(f"📡 *Broadcasting to {len(users)} users...*\n\nPlease wait...", 
                         call.message.chat.id, call.message.message_id,
                         parse_mode='Markdown')
    
    for user in users:
        try:
            broadcast_msg = f"""
*📢 TRACEX BROADCAST*

{broadcast_text}

━━━━━━━━━━━━━━━━
📞 *Support:* {ADMIN_USERNAME}
👥 *Group:* [Join Community]({GROUP_LINK})
"""
            bot.send_message(user[0], broadcast_msg, parse_mode='Markdown', disable_web_page_preview=True)
            success += 1
        except Exception as e:
            failed += 1
            print(f"Failed to send to {user[0]}: {e}")
        time.sleep(0.05)
    
    result_msg = f"""
✅ *Broadcast Complete!*

📊 *Statistics:*
• ✅ Sent: `{success}` users
• ❌ Failed: `{failed}` users
• 📝 Total: `{len(users)}` users

⏱️ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id,
                         reply_markup=main_menu_markup(), parse_mode='Markdown')
    
    del temp_data[user_id]

def confirm_giveaway(call):
    user_id = call.from_user.id
    if user_id != 7850023357:
        bot.answer_callback_query(call.id, "Unauthorized!", show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    if user_id not in temp_data:
        bot.edit_message_text("❌ Giveaway cancelled. No data found.", 
                            call.message.chat.id, call.message.message_id,
                            reply_markup=main_menu_markup())
        return
    
    credits = temp_data[user_id]['giveaway_credits']
    
    bot.edit_message_text(f"🎁 *Processing Giveaway...*\n\nGiving `{credits}` credits to all users...", 
                         call.message.chat.id, call.message.message_id,
                         parse_mode='Markdown')
    
    success, failed = giveaway_credits_to_all(credits, user_id)
    
    result_msg = f"""
🎉 *Giveaway Complete!* 🎉

✨ `{credits}` permanent credits given to each user!

📊 *Statistics:*
• ✅ Successful: `{success}` users
• ❌ Failed: `{failed}` users

💎 Total Credits Distributed: `{success * credits}`

⏱️ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    bot.edit_message_text(result_msg, call.message.chat.id, call.message.message_id,
                         reply_markup=main_menu_markup(), parse_mode='Markdown')
    
    del temp_data[user_id]

# ==================== START BOT ====================

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "TraceX Bot Running"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == "__main__":
    print("=" * 50)
    print(f"TraceX Lookup v{BOT_VERSION} is starting...")
    print(f"Admin ID: {ADMIN_ID}")
    print(f"Admin: {ADMIN_USERNAME}")
    print(f"Daily Credit Amount: {DAILY_FREE_CREDIT}")
    print(f"New User Credits: {FREE_CREDITS_ON_START}")
    print("=" * 50)
    
    init_db()
    
    # Start the daily credit checker thread
    print("🔄 Starting daily credit system...")
    # check_and_give_daily_credits()
    keep_alive()
    print("✅ Daily credit system disabled")
    
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("=" * 50)
    
    def signal_handler(sig, frame):
        print("\n🛑 Bot stopped by user")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
