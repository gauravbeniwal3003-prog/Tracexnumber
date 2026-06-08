"""
TraceX Website Promoter - Auto Broadcast System
Sends non-spammy website promotions to bot users at optimal times
Version: 1.0.0
"""

import os
import time
import random
import threading
from datetime import datetime, timedelta
import requests

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8525568503:AAHjydzj4bXdjVcS9c5jiL3CghFDfBePXXw")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

WEBSITE_URL = "https://tracexnumber.web.app"
ADMIN_ID = 7850023357

# Broadcast timing (in seconds)
BASE_INTERVAL = 2 * 60 * 60  # 2 hours
VARIATION = 15 * 60  # Add up to 15 minutes variation to avoid spam patterns

# Different message templates to rotate (prevents spam detection)
MESSAGE_TEMPLATES = [
    {
        "title": "⚡ FASTER ON WEB",
        "message": """🚀 *TRACEX WEB IS FASTER*

Website gives you:
✨ Flash speed lookups
💰 Lower credit costs
🎁 Regular exclusive offers
📱 Better mobile experience

👉 *Try now:* {url}

Same account, better experience!""",
        "button_text": "🌐 OPEN WEBSITE"
    },
    {
        "title": "💰 SAVE CREDITS",
        "message": """💎 *SAVE CREDITS ON WEB*

Website offers:
✅ 50% less credit cost
✅ Daily bonus offers
✅ Bulk lookup discounts
✅ No cooldown waits

👉 *Switch to web:* {url}

Your credits work on both platforms!""",
        "button_text": "🔗 VISIT WEBSITE"
    },
    {
        "title": "🎁 EXCLUSIVE OFFER",
        "message": """🎉 *SPECIAL WEB OFFER*

Active right now:
✨ Double credits on purchase
✨ Free 5 credits for web users
✨ Priority support
✨ Faster results

👉 *Claim offer:* {url}

Limited time!""",
        "button_text": "🎯 CLAIM OFFER"
    },
    {
        "title": "📱 BETTER EXPERIENCE",
        "message": """📱 *WEB VERSION IS BETTER*

Why switch?
⚡ Instant results
🔄 No message limits
💎 Regular bonus credits
🔍 Bulk search option
📊 Search history

👉 *Experience now:* {url}""",
        "button_text": "🚀 TRY NOW"
    },
    {
        "title": "⭐ USER FAVORITE",
        "message": """⭐ *WHY USERS LOVE WEB*

• 3x faster lookups
• 40% less credits
• Free daily searches
• 24/7 availability
• No bot restrictions

👉 *Join them:* {url}

Same login, better speed!""",
        "button_text": "💫 UPGRADE NOW"
    },
    {
        "title": "⚡ SPEED BOOST",
        "message": """🚀 *FLASH SPEED MODE*

Website delivers:
✨ Sub-second lookups
✨ Instant credit updates
✨ Real-time results
✨ No queuing

👉 *Enable speed:* {url}

Your account works instantly!""",
        "button_text": "🏃 GET SPEED"
    },
    {
        "title": "🎯 DAILY REWARDS",
        "message": """🎁 *DAILY WEB REWARDS*

Login on website daily:
✅ Free 2 credits every day
✅ Weekly bonus draws
✅ Referral credits
✅ Festival offers

👉 *Start collecting:* {url}

Don't miss your daily credits!""",
        "button_text": "📅 CLAIM REWARDS"
    }
]

# ==================== SUPABASE HELPER ====================

class SimpleSupabase:
    def __init__(self, url, key):
        self.url = url.rstrip('/')
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
    
    def get_all_users(self):
        """Get all non-banned users"""
        try:
            response = requests.get(
                f"{self.url}/rest/v1/telegram_users",
                headers=self.headers,
                params={"select": "telegram_user_id,is_banned", "is_banned": "eq.false"},
                timeout=10
            )
            if response.status_code == 200:
                return [user['telegram_user_id'] for user in response.json()]
            return []
        except Exception as e:
            print(f"Supabase error: {e}")
            return []

# ==================== BROADCAST MANAGER ====================

class WebsitePromoter:
    def __init__(self):
        self.supabase = SimpleSupabase(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
        self.last_broadcast_time = {}
        self.message_index = 0
        self.is_running = True
        self.stats = {
            "total_sent": 0,
            "total_failed": 0,
            "last_broadcast": None,
            "users_count": 0
        }
    
    def get_next_interval(self):
        """Get next broadcast interval with variation to avoid spam patterns"""
        variation = random.randint(-VARIATION, VARIATION)
        interval = BASE_INTERVAL + variation
        return max(60, interval)  # Never less than 1 minute
    
    def get_next_message(self, user_id):
        """Rotate messages and personalize"""
        template = MESSAGE_TEMPLATES[self.message_index % len(MESSAGE_TEMPLATES)]
        self.message_index += 1
        
        # Personalize message
        message = template["message"].replace("{url}", WEBSITE_URL)
        
        return {
            "title": template["title"],
            "message": message,
            "button_text": template["button_text"]
        }
    
    def send_telegram_message(self, user_id, message_data):
        """Send message to a single user"""
        try:
            # Create inline keyboard with website button
            keyboard = {
                "inline_keyboard": [[
                    {"text": message_data["button_text"], "url": WEBSITE_URL},
                    {"text": "🔙 MAIN MENU", "callback_data": "main_menu"}
                ]]
            }
            
            payload = {
                "chat_id": user_id,
                "text": message_data["message"],
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
                "disable_web_page_preview": False
            }
            
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return True, None
            else:
                error = response.json().get("description", "Unknown error")
                return False, error
                
        except Exception as e:
            return False, str(e)
    
    def should_send_to_user(self, user_id):
        """Check if user should receive message (anti-spam)"""
        last_time = self.last_broadcast_time.get(user_id)
        if not last_time:
            return True
        
        # Minimum 3 hours between messages to same user
        min_interval = 3 * 60 * 60
        return (datetime.now() - last_time).total_seconds() >= min_interval
    
    def broadcast_to_users(self, users):
        """Send broadcast to all users with rate limiting"""
        if not users:
            print("No users found")
            return
        
        print(f"\n{'='*50}")
        print(f"📢 Starting broadcast to {len(users)} users")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")
        
        message_data = self.get_next_message(None)
        sent = 0
        failed = 0
        skipped = 0
        
        for idx, user_id in enumerate(users):
            # Check if should send
            if not self.should_send_to_user(user_id):
                skipped += 1
                continue
            
            # Send message
            success, error = self.send_telegram_message(user_id, message_data)
            
            if success:
                sent += 1
                self.last_broadcast_time[user_id] = datetime.now()
                print(f"✅ Sent to {user_id}")
            else:
                failed += 1
                print(f"❌ Failed to {user_id}: {error}")
            
            # Rate limiting: 1 message per second (Telegram limit is 30/sec)
            time.sleep(1)
            
            # Progress update every 50 users
            if (idx + 1) % 50 == 0:
                print(f"📊 Progress: {idx+1}/{len(users)} (Sent: {sent}, Failed: {failed}, Skipped: {skipped})")
        
        # Update stats
        self.stats["total_sent"] += sent
        self.stats["total_failed"] += failed
        self.stats["last_broadcast"] = datetime.now()
        self.stats["users_count"] = len(users)
        
        print(f"\n{'='*50}")
        print(f"✅ Broadcast complete!")
        print(f"📤 Sent: {sent}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️ Skipped (recent): {skipped}")
        print(f"📊 Total sent all time: {self.stats['total_sent']}")
        print(f"{'='*50}\n")
        
        # Send report to admin
        self.send_admin_report(sent, failed, skipped, len(users))
    
    def send_admin_report(self, sent, failed, skipped, total):
        """Send broadcast report to admin"""
        try:
            report = f"""📊 *BROADCAST REPORT*

━━━━━━━━━━━━━━━━
👥 Total Users: `{total}`
✅ Delivered: `{sent}`
❌ Failed: `{failed}`
⏭️ Skipped: `{skipped}`
━━━━━━━━━━━━━━━━
📈 Total All Time: `{self.stats['total_sent']}`
⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🌐 Website: {WEBSITE_URL}"""
            
            keyboard = {
                "inline_keyboard": [[
                    {"text": "📊 VIEW STATS", "callback_data": "web_stats"},
                    {"text": "⏸️ PAUSE", "callback_data": "pause_broadcast"}
                ]]
            }
            
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": ADMIN_ID,
                    "text": report,
                    "parse_mode": "Markdown",
                    "reply_markup": keyboard
                },
                timeout=10
            )
        except Exception as e:
            print(f"Admin report failed: {e}")
    
    def run_continuous(self):
        """Main loop - runs broadcasts at optimized intervals"""
        print("🚀 Website Promoter Started")
        print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ Base Interval: {BASE_INTERVAL//3600} hours (+{VARIATION//60} min variation)")
        print(f"🌐 Website: {WEBSITE_URL}")
        print(f"{'='*50}\n")
        
        # Send startup notification to admin
        try:
            startup_msg = f"""✅ *Website Promoter Active*

⏰ Schedule: Every {BASE_INTERVAL//3600} hours
🎲 Variation: ±{VARIATION//60} minutes
🌐 Website: {WEBSITE_URL}

Messages will rotate through {len(MESSAGE_TEMPLATES)} templates
Users will receive max 8 messages per day

/status - Check current stats
/pause - Stop broadcasts
/resume - Resume broadcasts"""
            
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_ID, "text": startup_msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except:
            pass
        
        while self.is_running:
            try:
                # Get all users
                users = self.supabase.get_all_users() if self.supabase else []
                
                if users:
                    # Send broadcast
                    self.broadcast_to_users(users)
                else:
                    print(f"⚠️ No users found at {datetime.now()}")
                
                # Calculate next broadcast time
                interval = self.get_next_interval()
                next_time = datetime.now() + timedelta(seconds=interval)
                
                print(f"⏰ Next broadcast at: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"💤 Sleeping for {interval//60} minutes...\n")
                
                # Sleep until next broadcast (check every minute for stop signal)
                for _ in range(interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n🛑 Stopping promoter...")
                self.is_running = False
                break
            except Exception as e:
                print(f"❌ Error in broadcast loop: {e}")
                time.sleep(60)  # Wait 1 minute before retry
    
    def get_status(self):
        """Get current status"""
        return {
            "is_running": self.is_running,
            "total_sent": self.stats["total_sent"],
            "total_failed": self.stats["total_failed"],
            "last_broadcast": self.stats["last_broadcast"],
            "message_template_index": self.message_index % len(MESSAGE_TEMPLATES),
            "users_tracked": len(self.last_broadcast_time)
        }
    
    def stop(self):
        """Stop the promoter"""
        self.is_running = False
        print("🛑 Promoter stopped")

# ==================== TELEGRAM COMMANDS FOR ADMIN ====================

def handle_admin_commands():
    """Simple command handler for admin (runs in separate thread)"""
    last_update_id = 0
    
    while True:
        try:
            # Get updates
            response = requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=35
            )
            
            if response.status_code == 200:
                updates = response.json().get("result", [])
                
                for update in updates:
                    last_update_id = update["update_id"]
                    
                    # Check for message
                    if "message" in update:
                        message = update["message"]
                        user_id = message["from"]["id"]
                        text = message.get("text", "")
                        
                        # Only respond to admin
                        if user_id == ADMIN_ID:
                            if text == "/status":
                                status = promoter.get_status()
                                status_msg = f"""📊 *PROMOTER STATUS*

━━━━━━━━━━━━━━━━
🟢 Status: `{"Active" if status['is_running'] else "Stopped"}`
📤 Total Sent: `{status['total_sent']}`
❌ Total Failed: `{status['total_failed']}`
👥 Users Tracked: `{status['users_tracked']}`
📝 Next Template: `{status['message_template_index'] + 1}/{len(MESSAGE_TEMPLATES)}`
━━━━━━━━━━━━━━━━
⏰ Last Broadcast: `{status['last_broadcast'].strftime('%Y-%m-%d %H:%M:%S') if status['last_broadcast'] else 'Never'}`

🌐 Website: {WEBSITE_URL}"""
                                
                                requests.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": ADMIN_ID, "text": status_msg, "parse_mode": "Markdown"},
                                    timeout=10
                                )
                            
                            elif text == "/pause":
                                promoter.stop()
                                requests.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": ADMIN_ID, "text": "⏸️ Broadcasts paused. Send /resume to start again."},
                                    timeout=10
                                )
                            
                            elif text == "/resume":
                                if not promoter.is_running:
                                    promoter.is_running = True
                                    # Start new thread
                                    thread = threading.Thread(target=promoter.run_continuous, daemon=True)
                                    thread.start()
                                    requests.post(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                        json={"chat_id": ADMIN_ID, "text": "▶️ Broadcasts resumed!"},
                                        timeout=10
                                    )
                                else:
                                    requests.post(
                                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                        json={"chat_id": ADMIN_ID, "text": "⚠️ Promoter is already running!"},
                                        timeout=10
                                    )
                            
                            elif text == "/test":
                                # Test broadcast to admin only
                                test_msg = f"""🧪 *TEST BROADCAST*

This is a test message from website promoter.

🌐 Website: {WEBSITE_URL}

✨ Features:
• Flash speed
• Lower credits
• Regular offers

✅ Working correctly!"""
                                
                                keyboard = {
                                    "inline_keyboard": [[
                                        {"text": "🌐 VISIT WEBSITE", "url": WEBSITE_URL}
                                    ]]
                                }
                                
                                requests.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={
                                        "chat_id": ADMIN_ID,
                                        "text": test_msg,
                                        "parse_mode": "Markdown",
                                        "reply_markup": keyboard
                                    },
                                    timeout=10
                                )
                            
                            elif text == "/help":
                                help_msg = """📖 *WEBSITE PROMOTER COMMANDS*

/status - Show promoter status
/pause - Stop auto broadcasts
/resume - Start broadcasts again
/test - Send test message
/help - Show this help

━━━━━━━━━━━━━━━━
📊 *How it works*
• Broadcasts every ~2 hours
• Rotates through 7 message templates
• Users get max 8 messages/day
• Smart anti-spam protection
• Personalised with user's name

🌐 {url}""".replace("{url}", WEBSITE_URL)
                                
                                requests.post(
                                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                                    json={"chat_id": ADMIN_ID, "text": help_msg, "parse_mode": "Markdown"},
                                    timeout=10
                                )
            
            time.sleep(1)
            
        except Exception as e:
            print(f"Command handler error: {e}")
            time.sleep(5)

# ==================== MAIN ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 TRACEX WEBSITE PROMOTER")
    print("=" * 60)
    print(f"🌐 Website: {WEBSITE_URL}")
    print(f"⏰ Broadcast Interval: Every {BASE_INTERVAL//3600} hours")
    print(f"🎲 Variation: ±{VARIATION//60} minutes")
    print(f"📝 Message Templates: {len(MESSAGE_TEMPLATES)}")
    print("=" * 60)
    print("\n💡 Admin Commands:")
    print("  /status  - Check promoter status")
    print("  /pause   - Stop broadcasts")
    print("  /resume  - Start broadcasts")
    print("  /test    - Send test message")
    print("  /help    - Show help")
    print("=" * 60)
    
    # Initialize promoter
    promoter = WebsitePromoter()
    
    # Start command handler thread
    cmd_thread = threading.Thread(target=handle_admin_commands, daemon=True)
    cmd_thread.start()
    
    # Start promoter
    try:
        promoter.run_continuous()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        promoter.stop()
        print("✅ Shutdown complete")