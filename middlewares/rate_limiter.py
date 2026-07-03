"""
vault bot — rate limiting middleware
token bucket per user with configurable window using bounded TTLCache
"""

from __future__ import annotations
import time
import logging
from typing import Dict, List
from telegram import Update
from telegram.ext import ContextTypes
from cachetools import TTLCache
from config import cfg

log = logging.getLogger(__name__)

# Bounded in-memory cache to prevent memory exhaustion / leaks
_buckets: TTLCache[int, List[float]] = TTLCache(maxsize=10000, ttl=cfg.RATE_LIMIT_WINDOW)


async def rate_limit_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user:
        return True

    user_id = update.effective_user.id

    if cfg.is_admin(user_id, context.bot.id) or cfg.is_owner(user_id, context.bot.id):
        return True

    now = time.monotonic()
    window = cfg.RATE_LIMIT_WINDOW
    limit = cfg.RATE_LIMIT_MESSAGES

    bucket = _buckets.get(user_id, [])
    # Clean up older timestamps outside the current window
    bucket = [t for t in bucket if now - t < window]

    if len(bucket) >= limit:
        log.warning("rate limit hit: user=%d", user_id)
        if update.message:
            await update.message.reply_text(
                "⏳ ʏᴏᴜ'ʀᴇ sᴇɴᴅɪɴɢ ᴍᴇssᴀɢᴇs ᴛᴏᴏ ꜰᴀsᴛ.\n"
                f"ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴀ ꜰᴇᴡ sᴇᴄᴏɴᴅs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.",
            )
        return False

    bucket.append(now)
    _buckets[user_id] = bucket
    return True
