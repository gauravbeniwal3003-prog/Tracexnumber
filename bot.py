"""
TraceX Website Promoter - Auto Broadcast System
Sends non-spammy website promotions to bot users
Version: 2.0.0 - Production Ready
"""

import os
import time
import random
import threading
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8525568503:AAHjydzj4bXdjVcS9c5jiL3CghFDfBePXXw")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

WEBSITE_URL = "https://tracexnumber.web.app"
ADMIN_ID = int(os.getenv("ADMIN_ID", "7850023357"))

# Broadcast timing
BASE_INTERVAL = 2 * 60 * 60  # 2 hours
VARIATION = 15 * 60  # ±15 minutes variation

# Anti-spam: minimum 3 hours between messages to same user
MIN_USER_INTERVAL = 3 * 60 * 60

# Rate limiting: messages per second
MESSAGES_PER_SECOND = 1

# Message templates (rotating)
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

# ==================== SUPABASE CLIENT ====================

class SupabaseClient:
    """Simple Supabase client for fetching users"""
    
    def __init__(self, url: str, key: str):
        self.url = url.rstrip('/')
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
    
    def get_all_users(self) -> List[int]:
        """Get all non-banned users"""
        try:
            # Try to get from telegram_users table
            response = requests.get(
                f"{self.url}/rest/v1/telegram_users",
                headers=self.headers,
                params={"select": "telegram_user_id", "is_banned": "eq.false"},
                timeout=10
            )
            
            if response.status_code == 200:
                users = response.json()
                return [user['telegram_user_id'] for user in users]
            else:
                print(f"Supabase error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Supabase connection error: {e}")
            return []
    
    def get_user_count(self) -> int:
        """Get total user count"""
        try:
            response = requests.get(
                f"{self.url}/rest/v1/telegram_users",
                headers=self.headers,
                params={"select": "telegram_user_id", "is_banned": "eq.false"},
                timeout=10
            )
            if response.status_code == 200:
                return len(response.json())
            return 0
        except:
            return 0

# ==================== TELEGRAM BOT ====================

class TelegramBot:
    """Telegram API wrapper"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.last_update_id = 0
    
    def send_message(self, chat_id: int, text: str, reply_markup: dict = None) -> bool:
        """Send message to user"""
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
            
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"Send error to {chat_id}: {e}")
            return False
    
    def get_updates(self, timeout: int = 30) -> List[dict]:
        """Get updates for command handling"""
        try:
            params = {
                "offset": self.last_update_id + 1,
                "timeout": timeout,
                "allowed_updates": ["message", "callback_query"]
            }
            
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params=params,
                timeout=timeout + 5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    if updates:
                        self.last_update_id = updates[-1]["update_id"]
                    return updates
            
            return []
            
        except Exception as e:
            print(f"Get updates error: {e}")
            return []

# ==================== BROADCAST MANAGER ====================

class BroadcastManager:
    """Manages auto broadcasts to users"""
    
    def __init__(self, bot: TelegramBot, supabase: SupabaseClient):
        self.bot = bot
        self.supabase = supabase
        self.last_broadcast_time: Dict[int, datetime] = {}
        self.message_index = 0
        self.is_running = True
        self.is_paused = False
        
        # Statistics
        self.stats = {
            "total_sent": 0,
            "total_failed": 0,
            "total_skipped": 0,
            "last_broadcast": None,
            "broadcast_count": 0,
            "start_time": datetime.now()
        }
    
    def get_next_interval(self) -> int:
        """Get next broadcast interval with random variation"""
        variation = random.randint(-VARIATION, VARIATION)
        return max(60, BASE_INTERVAL + variation)
    
    def get_next_message(self) -> dict:
        """Get next message template (rotating)"""
        template = MESSAGE_TEMPLATES[self.message_index % len(MESSAGE_TEMPLATES)]
        self.message_index += 1
        
        # Create keyboard with website button
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": template["button_text"], "url": WEBSITE_URL},
                    {"text": "🔙 MENU", "callback_data": "main_menu"}
                ]
            ]
        }
        
        return {
            "text": template["message"].replace("{url}", WEBSITE_URL),
            "keyboard": keyboard,
            "title": template["title"]
        }
    
    def should_send_to_user(self, user_id: int) -> bool:
        """Check if user should receive message (anti-spam)"""
        last_time = self.last_broadcast_time.get(user_id)
        if not last_time:
            return True
        
        time_since = (datetime.now() - last_time).total_seconds()
        return time_since >= MIN_USER_INTERVAL
    
    def send_broadcast(self, users: List[int]) -> Dict:
        """Send broadcast to all users"""
        if not users:
            return {"sent": 0, "failed": 0, "skipped": 0}
        
        message_data = self.get_next_message()
        sent = 0
        failed = 0
        skipped = 0
        
        print(f"\n{'='*60}")
        print(f"📢 BROADCAST #{self.stats['broadcast_count'] + 1}")
        print(f"📝 Template: {message_data['title']}")
        print(f"👥 Total Users: {len(users)}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        for idx, user_id in enumerate(users, 1):
            # Check if paused
            if self.is_paused:
                print("⏸️ Broadcast paused")
                break
            
            # Check anti-spam
            if not self.should_send_to_user(user_id):
                skipped += 1
                if idx % 100 == 0:
                    print(f"📊 Progress: {idx}/{len(users)} (Sent: {sent}, Skipped: {skipped}, Failed: {failed})")
                continue
            
            # Send message
            success = self.bot.send_message(
                user_id,
                message_data["text"],
                message_data["keyboard"]
            )
            
            if success:
                sent += 1
                self.last_broadcast_time[user_id] = datetime.now()
                if sent % 10 == 0:
                    print(f"✅ Sent to {user_id}")
            else:
                failed += 1
                print(f"❌ Failed: {user_id}")
            
            # Rate limiting
            time.sleep(1 / MESSAGES_PER_SECOND)
            
            # Progress update
            if idx % 50 == 0:
                print(f"📊 Progress: {idx}/{len(users)} (Sent: {sent}, Skipped: {skipped}, Failed: {failed})")
        
        # Update stats
        self.stats["total_sent"] += sent
        self.stats["total_failed"] += failed
        self.stats["total_skipped"] += skipped
        self.stats["last_broadcast"] = datetime.now()
        self.stats["broadcast_count"] += 1
        
        print(f"\n{'='*60}")
        print(f"✅ BROADCAST COMPLETE")
        print(f"📤 Sent: {sent}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️ Skipped: {skipped}")
        print(f"📊 Total Sent All Time: {self.stats['total_sent']}")
        print(f"{'='*60}\n")
        
        return {"sent": sent, "failed": failed, "skipped": skipped}
    
    def send_admin_report(self, result: Dict):
        """Send report to admin"""
        try:
            uptime = datetime.now() - self.stats["start_time"]
            hours = uptime.total_seconds() // 3600
            
            report = f"""📊 *BROADCAST REPORT*

━━━━━━━━━━━━━━━━━━
📨 Just Sent: `{result['sent']}` users
❌ Failed: `{result['failed']}`
⏭️ Skipped: `{result['skipped']}`

━━━━━━━━━━━━━━━━━━
📈 ALL TIME STATS
📤 Total Sent: `{self.stats['total_sent']}`
❌ Total Failed: `{self.stats['total_failed']}`
⏭️ Total Skipped: `{self.stats['total_skipped']}`
🔄 Broadcasts: `{self.stats['broadcast_count']}`

━━━━━━━━━━━━━━━━━━
⏰ Uptime: `{int(hours)} hours`
🌐 Website: {WEBSITE_URL}

/status - View full stats
/pause - Pause broadcasts
/resume - Resume broadcasts"""
            
            self.bot.send_message(ADMIN_ID, report)
            
        except Exception as e:
            print(f"Admin report error: {e}")
    
    def get_status(self) -> Dict:
        """Get current status"""
        uptime = datetime.now() - self.stats["start_time"]
        
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "total_sent": self.stats["total_sent"],
            "total_failed": self.stats["total_failed"],
            "total_skipped": self.stats["total_skipped"],
            "broadcast_count": self.stats["broadcast_count"],
            "last_broadcast": self.stats["last_broadcast"],
            "uptime_seconds": uptime.total_seconds(),
            "next_template": (self.message_index % len(MESSAGE_TEMPLATES)) + 1,
            "total_templates": len(MESSAGE_TEMPLATES),
            "users_tracked": len(self.last_broadcast_time)
        }
    
    def pause(self):
        """Pause broadcasts"""
        self.is_paused = True
        print("⏸️ Broadcasts paused")
    
    def resume(self):
        """Resume broadcasts"""
        self.is_paused = False
        print("▶️ Broadcasts resumed")
    
    def stop(self):
        """Stop the manager"""
        self.is_running = False
        print("🛑 Broadcast manager stopped")
    
    def run(self):
        """Main broadcast loop"""
        print("🚀 Website Promoter Started")
        print(f"📅 Start: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏰ Interval: {BASE_INTERVAL//3600} hours ±{VARIATION//60} min")
        print(f"🛡️ Anti-spam: {MIN_USER_INTERVAL//3600} hours between messages")
        print(f"📝 Templates: {len(MESSAGE_TEMPLATES)}")
        print(f"🌐 Website: {WEBSITE_URL}")
        print(f"{'='*60}\n")
        
        # Send startup notification
        self.bot.send_message(
            ADMIN_ID,
            f"✅ *Website Promoter Active*\n\n"
            f"⏰ Schedule: Every {BASE_INTERVAL//3600} hours\n"
            f"🎲 Variation: ±{VARIATION//60} minutes\n"
            f"🌐 Website: {WEBSITE_URL}\n\n"
            f"Commands:\n"
            f"/status - View stats\n"
            f"/pause - Pause broadcasts\n"
            f"/resume - Resume broadcasts\n"
            f"/test - Send test message"
        )
        
        while self.is_running:
            try:
                if not self.is_paused:
                    # Get users
                    users = self.supabase.get_all_users()
                    
                    if users:
                        # Send broadcast
                        result = self.send_broadcast(users)
                        # Send report to admin
                        self.send_admin_report(result)
                    else:
                        print(f"⚠️ No users found at {datetime.now()}")
                        # Try to get count for debugging
                        count = self.supabase.get_user_count()
                        print(f"📊 User count from API: {count}")
                
                # Wait for next broadcast
                interval = self.get_next_interval()
                next_time = datetime.now() + timedelta(seconds=interval)
                
                status = "PAUSED" if self.is_paused else "ACTIVE"
                print(f"⏰ [{status}] Next broadcast at: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"💤 Sleeping for {interval//60} minutes...\n")
                
                # Sleep with periodic checks
                for _ in range(interval):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n🛑 Received interrupt signal")
                break
            except Exception as e:
                print(f"❌ Broadcast loop error: {e}")
                time.sleep(60)  # Wait 1 minute before retry
        
        print("🛑 Broadcast manager stopped")

# ==================== COMMAND HANDLER ====================

class CommandHandler:
    """Handles admin commands from Telegram"""
    
    def __init__(self, bot: TelegramBot, manager: BroadcastManager):
        self.bot = bot
        self.manager = manager
        self.is_running = True
    
    def handle_command(self, text: str, user_id: int):
        """Handle incoming command"""
        if user_id != ADMIN_ID:
            return
        
        cmd = text.lower().strip()
        
        if cmd == "/status":
            self.send_status()
        
        elif cmd == "/pause":
            self.manager.pause()
            self.bot.send_message(ADMIN_ID, "⏸️ Broadcasts paused. Send /resume to start again.")
        
        elif cmd == "/resume":
            self.manager.resume()
            self.bot.send_message(ADMIN_ID, "▶️ Broadcasts resumed!")
        
        elif cmd == "/test":
            self.send_test()
        
        elif cmd == "/help":
            self.send_help()
        
        elif cmd == "/stats":
            self.send_detailed_stats()
    
    def send_status(self):
        """Send current status to admin"""
        status = self.manager.get_status()
        
        uptime_hours = status["uptime_seconds"] / 3600
        
        status_msg = f"""📊 *PROMOTER STATUS*

━━━━━━━━━━━━━━━━━━
🟢 Status: `{"Active" if status["is_running"] and not status["is_paused"] else "Paused" if status["is_paused"] else "Stopped"}`
📤 Total Sent: `{status["total_sent"]}`
❌ Total Failed: `{status["total_failed"]}`
⏭️ Total Skipped: `{status["total_skipped"]}`
🔄 Broadcasts Run: `{status["broadcast_count"]}`

━━━━━━━━━━━━━━━━━━
📝 Next Template: `{status["next_template"]}/{status["total_templates"]}`
👥 Users Tracked: `{status["users_tracked"]}`

━━━━━━━━━━━━━━━━━━
⏰ Uptime: `{uptime_hours:.1f} hours`
🌐 Website: {WEBSITE_URL}

/help - Show all commands"""
        
        self.bot.send_message(ADMIN_ID, status_msg)
    
    def send_detailed_stats(self):
        """Send detailed statistics"""
        # Try to get user count from database
        user_count = self.manager.supabase.get_user_count()
        
        stats_msg = f"""📈 *DETAILED STATISTICS*

━━━━━━━━━━━━━━━━━━
👥 Total Users in DB: `{user_count}`
📤 Messages Sent: `{self.manager.stats['total_sent']}`
📊 Avg per Broadcast: `{self.manager.stats['total_sent'] // max(1, self.manager.stats['broadcast_count'])}`

━━━━━━━━━━━━━━━━━━
🎯 CONVERSION EXPECTED
• Daily Reach: ~{user_count // 3} users
• Weekly Reach: ~{user_count} users

━━━━━━━━━━━━━━━━━━
⚙️ CONFIGURATION
• Interval: {BASE_INTERVAL//3600} hours
• Anti-spam: {MIN_USER_INTERVAL//3600} hours
• Templates: {len(MESSAGE_TEMPLATES)}

🌐 {WEBSITE_URL}"""
        
        self.bot.send_message(ADMIN_ID, stats_msg)
    
    def send_test(self):
        """Send test message to admin"""
        test_msg = f"""🧪 *TEST BROADCAST*

This is a test message from the website promoter.

✅ System is working correctly!

🌐 Website: {WEBSITE_URL}

Features:
✨ Flash speed lookups
💰 Lower credit costs
🎁 Regular offers
📱 Better experience

*All systems operational*"""
        
        keyboard = {
            "inline_keyboard": [[
                {"text": "🌐 VISIT WEBSITE", "url": WEBSITE_URL}
            ]]
        }
        
        self.bot.send_message(ADMIN_ID, test_msg, keyboard)
    
    def send_help(self):
        """Send help message"""
        help_msg = f"""📖 *WEBSITE PROMOTER COMMANDS*

━━━━━━━━━━━━━━━━━━
/status - Show current status
/stats - Show detailed statistics
/pause - Pause auto broadcasts
/resume - Resume broadcasts
/test - Send test message
/help - Show this help

━━━━━━━━━━━━━━━━━━
📊 HOW IT WORKS
• Broadcasts every ~2 hours
• Rotates through {len(MESSAGE_TEMPLATES)} templates
• Anti-spam: {MIN_USER_INTERVAL//3600} hours between messages
• Random variation: ±{VARIATION//60} minutes

━━━━━━━━━━━━━━━━━━
🌐 Website: {WEBSITE_URL}"""
        
        self.bot.send_message(ADMIN_ID, help_msg)
    
    def run(self):
        """Run command handler loop"""
        print("✅ Command handler started")
        
        while self.is_running:
            try:
                updates = self.bot.get_updates(timeout=30)
                
                for update in updates:
                    # Handle messages
                    if "message" in update:
                        message = update["message"]
                        user_id = message["from"]["id"]
                        text = message.get("text", "")
                        
                        if text.startswith("/"):
                            self.handle_command(text, user_id)
                    
                    # Handle callback queries
                    elif "callback_query" in update:
                        callback = update["callback_query"]
                        user_id = callback["from"]["id"]
                        # You can add callback handling here if needed
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Command handler error: {e}")
                time.sleep(5)
    
    def stop(self):
        """Stop command handler"""
        self.is_running = False

# ==================== HEALTH CHECK SERVER ====================

def start_health_server(port: int):
    """Start a simple HTTP server for health checks"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/' or self.path == '/health':
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
            else:
                self.send_response(404)
                self.end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress logs
    
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"✅ Health check server started on port {port}")
    server.serve_forever()

# ==================== MAIN ====================

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Received shutdown signal")
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("🚀 TRACEX WEBSITE PROMOTER v2.0")
    print("=" * 60)
    print(f"🌐 Website: {WEBSITE_URL}")
    print(f"⏰ Interval: Every {BASE_INTERVAL//3600} hours (±{VARIATION//60} min)")
    print(f"📝 Templates: {len(MESSAGE_TEMPLATES)}")
    print(f"🛡️ Anti-spam: {MIN_USER_INTERVAL//3600} hours between messages")
    print("=" * 60)
    print("\n💡 Admin Commands (send in Telegram):")
    print("  /status  - Current status")
    print("  /stats   - Detailed statistics")
    print("  /pause   - Stop broadcasts")
    print("  /resume  - Start broadcasts")
    print("  /test    - Send test message")
    print("  /help    - Show help")
    print("=" * 60)
    
    # Start health check server for Render (if PORT env is set)
    render_port = os.getenv("PORT")
    if render_port:
        port = int(render_port)
        health_thread = threading.Thread(target=start_health_server, args=(port,), daemon=True)
        health_thread.start()
        print(f"✅ Render health check enabled on port {port}")
    
    # Initialize components
    bot = TelegramBot(BOT_TOKEN)
    supabase = SupabaseClient(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
    
    if not supabase:
        print("❌ ERROR: SUPABASE_URL and SUPABASE_KEY required!")
        print("Set environment variables and restart.")
        sys.exit(1)
    
    # Create broadcast manager
    manager = BroadcastManager(bot, supabase)
    
    # Create command handler
    command_handler = CommandHandler(bot, manager)
    
    # Start command handler in background
    cmd_thread = threading.Thread(target=command_handler.run, daemon=True)
    cmd_thread.start()
    
    # Run broadcast manager (blocks)
    try:
        manager.run()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        manager.stop()
        command_handler.stop()
        print("✅ Shutdown complete")
        sys.exit(0)