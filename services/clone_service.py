"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — bot clone service
manages starting, stopping, and running multi-bot instances dynamically
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
import httpx
from telegram import Update
from telegram.ext import Application, ApplicationBuilder
from database import clones
from config import cfg

log = logging.getLogger("vault.clone")


class BotCloneService:
    _active_apps: Dict[int, Application] = {}
    _clone_owners: Dict[int, int] = {}

    @staticmethod
    def get_owner(bot_id: int) -> Optional[int]:
        return BotCloneService._clone_owners.get(bot_id)

    @staticmethod
    async def start_all() -> None:
        """Start all active clone bots from database on system startup."""
        try:
            cursor = clones().find()
            async for doc in cursor:
                try:
                    await BotCloneService._start_bot(doc["token"], doc["owner_id"])
                except Exception as e:
                    log.error("failed to start clone bot %s: %s", doc.get("username", "unknown"), e)
        except Exception as e:
            log.error("failed to query clone bots: %s", e)

    @staticmethod
    async def stop_all() -> None:
        """Stop all active clone bots on system shutdown."""
        log.info("stopping all active clone bots...")
        bot_ids = list(BotCloneService._active_apps.keys())
        for bot_id in bot_ids:
            try:
                await BotCloneService._stop_bot(bot_id)
            except Exception as e:
                log.error("failed to stop clone bot %d: %s", bot_id, e)

    @staticmethod
    async def add_clone(token: str, owner_id: int, creator_id: int) -> Dict[str, Any]:
        """Validate, register, and start a new clone bot."""
        # 1. Validate token with Telegram getMe API
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if resp.status_code != 200:
                raise ValueError("Invalid bot token.")
            data = resp.json()
            if not data.get("ok"):
                raise ValueError("Invalid bot token.")
            bot_info = data["result"]
            bot_id = bot_info["id"]
            username = bot_info["username"]

        # 2. Check if already registered
        existing = await clones().find_one({"bot_id": bot_id})
        if existing:
            raise ValueError(f"Bot @{username} is already registered.")

        # 3. Save to database
        doc = {
            "token": token,
            "bot_id": bot_id,
            "owner_id": owner_id,
            "creator_id": creator_id,
            "username": username,
        }
        await clones().insert_one(doc)

        # 4. Start the bot in background
        await BotCloneService._start_bot(token, owner_id)
        return doc

    @staticmethod
    async def remove_clone(bot_id: int) -> bool:
        """Stop and unregister a clone bot."""
        await BotCloneService._stop_bot(bot_id)
        res = await clones().delete_one({"bot_id": bot_id})
        return res.deleted_count > 0

    @staticmethod
    async def list_user_clones(creator_id: int) -> List[Dict[str, Any]]:
        """List all clone bots created by a specific user."""
        cursor = clones().find({"creator_id": creator_id})
        return await cursor.to_list(100)

    @staticmethod
    async def _start_bot(token: str, owner_id: int) -> None:
        """Start a clone bot application and polling thread."""
        from main import _register_handlers
        from telegram.request import HTTPXRequest

        # Configure connection pooling requests client
        request_client = HTTPXRequest(
            connection_pool_size=16,
            connect_timeout=5.0,
            read_timeout=10.0,
            write_timeout=10.0,
            pool_timeout=5.0
        )

        app = (
            ApplicationBuilder()
            .token(token)
            .request(request_client)
            .concurrent_updates(True)
            .build()
        )

        # Register same handlers as the main bot
        _register_handlers(app)

        await app.initialize()
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

        bot_id = app.bot.id
        BotCloneService._active_apps[bot_id] = app
        BotCloneService._clone_owners[bot_id] = owner_id
        log.info("clone bot started: @%s (owner=%d)", app.bot.username, owner_id)

    @staticmethod
    async def _stop_bot(bot_id: int) -> None:
        """Stop a running clone bot application."""
        app = BotCloneService._active_apps.pop(bot_id, None)
        BotCloneService._clone_owners.pop(bot_id, None)
        if app:
            log.info("stopping clone bot: @%s", app.bot.username)
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
