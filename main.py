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
from telegram.ext import Application, ApplicationBuilder

from config import cfg
from database import connect, disconnect
from utils.logger import system_log
from utils import scheduler
import handlers

log = logging.getLogger("vault.main")


def _register_handlers(app: Application) -> None:
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
