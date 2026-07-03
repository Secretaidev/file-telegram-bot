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
        handlers.clone,
    ):
        for handler in module.get_handlers():
            app.add_handler(handler)

    app.add_error_handler(handlers.error.error_handler)

    # ── text input handlers in separate groups to avoid conflicts ─────────────
    # All state-based text handlers are restricted to PRIVATE chats.
    # In groups the bot only reacts to its own commands (and @mentions for AI).
    from handlers.file_ops import handle_rename_input
    from handlers.folder import handle_folder_name
    from handlers.vault import handle_vault_input
    from handlers.search import handle_search_text
    from handlers.admin import handle_broadcast, handle_admin_search
    from handlers.premium import handle_payment_screenshot
    from handlers.clone import handle_bot_token_input, handle_clone_owner_input

    _private_text = filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE
    _private_all  = filters.ALL  & ~filters.COMMAND & filters.ChatType.PRIVATE

    app.add_handler(MessageHandler(_private_text, handle_rename_input), group=1)
    app.add_handler(MessageHandler(_private_text, handle_folder_name), group=2)
    app.add_handler(MessageHandler(_private_text, handle_vault_input), group=3)
    app.add_handler(MessageHandler(_private_text, handle_search_text), group=4)
    app.add_handler(MessageHandler(_private_all,  handle_broadcast), group=5)
    app.add_handler(MessageHandler(_private_text, handle_admin_search), group=7)
    app.add_handler(MessageHandler(_private_text, handle_bot_token_input), group=8)
    app.add_handler(MessageHandler(_private_text, handle_clone_owner_input), group=9)

    # Payment screenshot — private chats only
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.IMAGE) & filters.ChatType.PRIVATE,
            handle_payment_screenshot,
        ),
        group=6,
    )

    # AI assistant — group 10 so all state-based handlers (1-7) run first.
    for handler in handlers.ai.get_handlers():
        app.add_handler(handler, group=10)

    log.info("all handlers registered")


async def _set_commands(app: Application) -> None:
    commands = [
        BotCommand("start",       "ᴍᴀɪɴ ᴍᴇɴᴜ"),
        BotCommand("upload",      "ᴜᴘʟᴏᴀᴅ ᴀ ꜰɪʟᴇ"),
        BotCommand("search",      "sᴇᴀʀᴄʜ ʏᴏᴜʀ ꜰɪʟᴇs"),
        BotCommand("vault",       "ᴏᴘᴇɴ ᴠᴀᴜʟᴛ"),
        BotCommand("premium",     "ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs"),
        BotCommand("ai",          "ᴛᴏɢɢʟᴇ ᴀɪ ᴀssɪsᴛᴀɴᴛ ᴏɴ/ᴏꜰꜰ"),
        BotCommand("admin",       "ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ"),
        BotCommand("maintenance", "ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ ᴛᴏɢɢʟᴇ"),
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

    # Start all active clone bots in background
    from services import BotCloneService
    asyncio.create_task(BotCloneService.start_all())

    log.info("startup complete")


async def _on_shutdown(app: Application) -> None:
    scheduler.stop()
    from services import BotCloneService
    await BotCloneService.stop_all()
    await disconnect()
    await system_log(app.bot, "⛔ vault bot stopped")
    log.info("shutdown complete")


def main() -> None:
    from telegram.request import HTTPXRequest
    
    # Configure custom HTTPX request client for high concurrency and resilience
    request_client = HTTPXRequest(
        connection_pool_size=128,  # Increase pool size for concurrent updates
        connect_timeout=5.0,
        read_timeout=10.0,
        write_timeout=10.0,
        pool_timeout=5.0
    )

    app = (
        ApplicationBuilder()
        .token(cfg.BOT_TOKEN)
        .request(request_client)
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
