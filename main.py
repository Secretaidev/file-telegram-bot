"""
vault bot — main application entry point
initialises db, registers handlers, starts polling
"""

import asyncio
import logging
import signal
import sys

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

from telegram import Update, BotCommand
from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters

from config import cfg
from database import connect, disconnect
from utils.logger import system_log
from utils import scheduler
import handlers

log = logging.getLogger("vault.main")


def _register_handlers(app: Application) -> None:
    # ── group 0: command + callback handlers ──────────────────────────────────
    for module in (
        handlers.start,
        handlers.upload,
        handlers.file_ops,
        handlers.search,
        handlers.folder,
        handlers.vault,
        handlers.share,
        handlers.premium,
        handlers.admin,
        handlers.favorites,
        handlers.stats,
    ):
        for handler in module.get_handlers():
            app.add_handler(handler)

    app.add_error_handler(handlers.error.error_handler)

    # ── text input handlers in separate groups to avoid conflicts ─────────────
    # Each handler checks its own state guard and returns early if not active.
    # Putting them in distinct groups ensures all are checked per text message.
    from handlers.file_ops import handle_rename_input
    from handlers.folder import handle_folder_name
    from handlers.vault import handle_vault_input
    from handlers.search import handle_search_text
    from handlers.admin import handle_broadcast, handle_admin_search
    from handlers.premium import handle_payment_screenshot

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rename_input), group=1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_folder_name), group=2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vault_input), group=3)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_text), group=4)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_broadcast), group=5)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_search), group=7)

    # Payment screenshot must be in a separate group so that handle_upload
    # (group 0) can return early when awaiting_screenshot is set, and this
    # handler processes the photo instead. Group 6 avoids any overlap with
    # the text-input groups (1-5).
    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_payment_screenshot),
        group=6,
    )

    log.info("all handlers registered")


async def _set_commands(app: Application) -> None:
    commands = [
        BotCommand("start",   "ᴍᴀɪɴ ᴍᴇɴᴜ"),
        BotCommand("upload",  "ᴜᴘʟᴏᴀᴅ ᴀ ꜰɪʟᴇ"),
        BotCommand("search",  "sᴇᴀʀᴄʜ ʏᴏᴜʀ ꜰɪʟᴇs"),
        BotCommand("vault",   "ᴏᴘᴇɴ ᴠᴀᴜʟᴛ"),
        BotCommand("premium", "ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs"),
        BotCommand("admin",   "ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ"),
    ]
    await app.bot.set_my_commands(commands)
    log.info("bot commands set")


async def _on_startup(app: Application) -> None:
    await connect()
    await _set_commands(app)
    # Cache actual bot username so deep-links are always correct
    from utils.helpers import set_bot_username
    me = await app.bot.get_me()
    set_bot_username(me.username)
    log.info("bot username: @%s", me.username)
    scheduler.start(app.bot)
    await system_log(app.bot, "🚀 vault bot started")
    log.info("startup complete")


async def _on_shutdown(app: Application) -> None:
    scheduler.stop()
    await disconnect()
    await system_log(app.bot, "⛔ vault bot stopped")
    log.info("shutdown complete")


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(cfg.BOT_TOKEN)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .concurrent_updates(True)
        .build()
    )

    _register_handlers(app)

    log.info("starting polling…")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
