"""
vault bot — channel membership middleware
restricts bot access until user joins required channels
"""

from __future__ import annotations
import logging
from typing import List, Tuple
from telegram import Update, Bot
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from config import cfg
from utils.keyboards import join_channels

log = logging.getLogger(__name__)


async def is_member(bot: Bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(f"@{channel}", user_id)
        return member.status not in ("left", "kicked", "restricted")
    except TelegramError as e:
        log.warning("membership check failed for @%s: %s", channel, e)
        return True


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not cfg.REQUIRED_CHANNELS:
        return True

    user = update.effective_user
    if not user:
        return True

    if cfg.is_admin(user.id):
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
