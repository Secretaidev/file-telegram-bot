"""
vault bot — rate limiting middleware
token bucket per user with configurable window
"""

from __future__ import annotations
import time
import logging
from collections import defaultdict
from typing import Dict, List
from telegram import Update
from telegram.ext import ContextTypes
from config import cfg

log = logging.getLogger(__name__)

_buckets: Dict[int, List[float]] = defaultdict(list)


async def rate_limit_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_user:
        return True

    user_id = update.effective_user.id

    if cfg.is_admin(user_id) or cfg.is_owner(user_id):
        return True

    now = time.monotonic()
    window = cfg.RATE_LIMIT_WINDOW
    limit = cfg.RATE_LIMIT_MESSAGES

    bucket = _buckets[user_id]
    _buckets[user_id] = [t for t in bucket if now - t < window]

    if len(_buckets[user_id]) >= limit:
        log.warning("rate limit hit: user=%d", user_id)
        if update.message:
            await update.message.reply_text(
                "⏳ ʏᴏᴜ'ʀᴇ sᴇɴᴅɪɴɢ ᴍᴇssᴀɢᴇs ᴛᴏᴏ ꜰᴀsᴛ.\n"
                f"ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ᴀ ꜰᴇᴡ sᴇᴄᴏɴᴅs ᴀɴᴅ ᴛʀʏ ᴀɢᴀɪɴ.",
            )
        return False

    _buckets[user_id].append(now)
    return True
