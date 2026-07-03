"""
vault bot — channel membership middleware
restricts bot access until user joins required channels with in-memory caching
"""

from __future__ import annotations
import logging
from typing import List, Tuple
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from cachetools import TTLCache
from config import cfg
from utils.keyboards import join_channels

log = logging.getLogger(__name__)

# Cache channel membership status for 5 minutes to prevent hitting Telegram API repeatedly
_membership_cache: TTLCache[Tuple[int, str], bool] = TTLCache(maxsize=10000, ttl=300)


def invalidate_membership_cache(user_id: int) -> None:
    """Invalidate membership cache for a user so that the next check is performed live."""
    for key in list(_membership_cache.keys()):
        if key[0] == user_id:
            _membership_cache.pop(key, None)


async def is_member(bot: Bot, user_id: int, channel: str) -> bool:
    cache_key = (user_id, channel)
    cached = _membership_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        member = await bot.get_chat_member(f"@{channel}", user_id)
        status = member.status not in ("left", "kicked", "restricted")
        _membership_cache[cache_key] = status
        return status
    except TelegramError as e:
        log.warning("membership check failed for @%s: %s", channel, e)
        # Fallback to True to prevent locking out user on temporary Telegram errors
        return True


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not cfg.REQUIRED_CHANNELS:
        return True
    user = update.effective_user
    if not user:
        return True
    if cfg.is_owner(user.id, context.bot.id) or cfg.is_admin(user.id, context.bot.id):
        return True

    bot = context.bot
    not_joined: List[Tuple[str, str]] = []

    for channel in cfg.REQUIRED_CHANNELS:
        if not await is_member(bot, user.id, channel):
            invite_url = f"https://t.me/{channel}"
            not_joined.append((channel, invite_url))

    if not_joined:
        text = (
            "📢 ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴛʜᴇ ꜰᴏʟʟᴏᴡɪɴɢ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴜsᴇ ᴛʜᴇ ʙᴏᴛ:\n\n"
            + "\n".join(f"• @{ch}" for ch, _ in not_joined)
            + "\n\nᴀꜰᴛᴇʀ ᴊᴏɪɴɪɴɢ, ᴛᴀᴘ ✅ ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ."
        )
        markup = join_channels(not_joined)
        if update.message:
            await update.message.reply_text(text, reply_markup=markup)
        elif update.callback_query:
            await update.callback_query.answer("please join required channels first!", show_alert=True)
            await update.callback_query.message.reply_text(text, reply_markup=markup)
        return False

    return True
