import asyncio
import importlib
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, idle, filters
import logging

# Fix file descriptor limit
if sys.platform != "win32":
    try:
        import resource
        _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        _target = min(65536, _hard)
        if _soft < _target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (_target, _hard))
    except:
        pass

from config import BOT_TOKEN, OWNER_ID, SUDO_USERS, SESSION
from utils.database import Database
from music.downloader import MusicDownloader

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('clonify.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global instances
app = Client(SESSION, bot_token=BOT_TOKEN, in_memory=True, workers=4)
db = Database()
music_dl = MusicDownloader()

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Render health check endpoint"""
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Clonify Music Bot is running perfectly!')
    
    def log_message(self, format, *args):
        pass  # Silent logs

def run_http_server():
    """HTTP server for Render health checks"""
    try:
        port = int(os.environ.get("PORT", 8000))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🌐 HTTP health check server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server error: {e}")

# Simple handlers
async def start_cmd(client, message):
    await message.reply("""
🎵 **Clonify Music Bot** v2.0

**Commands:**
`.play <YouTube link>` - Play music
`.playlist` - Show queue
`.pause` - Pause music
`.resume` - Resume
`.skip` - Next song

**Owner Commands:**
`/panel` - Admin dashboard
`/addsudo <id>` - Add sudo
`/broadcast <msg>` - Broadcast
    """)

async def play_cmd(client, message):
    if len(message.command) < 2:
        await message.reply("❌ **Usage:** `.play <YouTube link>`")
        return
    
    url = message.command[1]
    await message.reply("⏳ **Downloading music...**")
    
    try:
        music_info = await music_dl.download(url, message.chat.id)
        await message.reply(f"✅ **Playing:** {music_info['title']}")
    except Exception as e:
        await message.reply(f"❌ **Error:** {str(e)}")

async def panel_cmd(client, message):
    if message.from_user.id not in [OWNER_ID] + SUDO_USERS:
        return
    
    stats = f"""
🔥 **Clonify Admin Panel**

**Bot Stats:**
• Owner: `{OWNER_ID}`
• Sudo Users: `{len(SUDO_USERS)}`
• Uptime: Live

**Controls:**
`/addsudo <user_id>`
`/broadcast <message>`
`/restart`
    """
    await message.reply(stats)

async def main():
    try:
        # 1. Validate config
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN missing in environment!")
            return
        
        logger.info("🔍 Starting Clonify Music Bot...")

        # 2. Init database
        await db.init_db()
        logger.info("✅ Database initialized")

        # 3. Start HTTP server (Render health check)
        http_thread = threading.Thread(target=run_http_server, daemon=True)
        http_thread.start()
        logger.info("🌐 HTTP server started")

        # 4. Start main bot
        await app.start()
        logger.info("✅ Main bot connected")

        # 5. Load sudo users
        sudoers = await db.get_sudoers()
        logger.info(f"👑 Loaded {len(sudoers)} sudo users")

        # 6. Register command handlers
        app.on_message(filters.command("start") & filters.private)(start_cmd)
        app.on_message(filters.command("help"))(start_cmd)
        app.on_message(filters.command("play", prefixes="."))(play_cmd)
        app.on_message(filters.command("panel", prefixes="/"))(panel_cmd)
        app.on_message(filters.command("playlist", prefixes="."))(lambda c,m: m.reply("📋 Queue system coming soon!"))

        logger.info("🎉 Clonify Music Bot fully loaded!")
        logger.info("📱 Ready! Commands: .play, /panel")
        logger.info("🌐 Health check: http://localhost:8000")
        
        # 7. Keep bot running
        await idle()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Critical error: {e}", exc_info=True)
    finally:
        await app.stop()
        logger.info("🔴 Bot shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
