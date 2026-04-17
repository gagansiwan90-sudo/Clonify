import asyncio
import importlib
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, idle, filters
import logging

# Fix file descriptor limit (Linux)
if sys.platform != "win32":
    try:
        import resource
        _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        _target = min(65536, _hard)
        if _soft < _target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (_target, _hard))
    except:
        pass

from config import BOT_TOKEN, OWNER_ID, SESSION
from utils.database import Database
from handlers import start, music, admin, player
import music.downloader

# Logging
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
app = Client(SESSION, bot_token=BOT_TOKEN, in_memory=True)
db = Database()
music_dl = music.downloader.MusicDownloader()

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Clonify Music Bot is running perfectly!')
    
    def log_message(self, format, *args):
        pass  # Silent logs

def run_http_server():
    """Render health check server"""
    try:
        port = int(os.environ.get("PORT", 8000))
        server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
        logger.info(f"🌐 HTTP server started on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"HTTP server error: {e}")

async def main():
    try:
        # 1. Validate config
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN missing!")
            return
        
        logger.info("🔍 Validating configuration...")

        # 2. Init database
        await db.init_db()
        logger.info("✅ Database connected")

        # 3. Start HTTP server (Render health check)
        http_thread = threading.Thread(target=run_http_server, daemon=True)
        http_thread.start()
        logger.info("🌐 HTTP server thread started")

        # 4. Boot main bot
        await app.start()
        logger.info("✅ Main bot started")

        # 5. Load sudo users
        sudoers = await db.get_sudoers()
        logger.info(f"👑 Loaded {len(sudoers)} sudo users")

        # 6. Register all handlers
        app.on_message(filters.command("start") & filters.private)(start.start_cmd)
        app.on_message(filters.command("help"))(start.help_cmd)
        app.on_message(filters.command("play", prefixes="."))(music.play_cmd)
        app.on_message(filters.command("playlist", prefixes="."))(music.playlist_cmd)
        app.on_message(filters.command("panel", prefixes="."))(admin.panel_cmd)
        app.on_message(filters.command("addsudo"))(admin.add_sudo_cmd)
        app.on_message(filters.command("broadcast"))(admin.broadcast_cmd)

        logger.info("🎉 Clonify Music Bot fully loaded!")
        logger.info("📱 Commands ready: .play, .playlist, .panel")
        
        # 7. Keep running
        await idle()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Error: {e}", exc_info=True)
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
