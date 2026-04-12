"""
vault bot — authentication middleware
ensures user exists in db, checks ban status, updates last_seen
"""

from __future__ import annotations
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import users, user_doc, Role
from config import cfg

log = logging.getLogger(__name__)


async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        # Channel posts, anonymous admin messages, etc. — skip silently
        return False

    doc = await users().find_one({"user_id": user.id})

    if doc is None:
        role = Role.OWNER.value if cfg.is_owner(user.id) else (
            Role.ADMIN.value if cfg.is_admin(user.id) else Role.USER.value
        )
        new_doc = user_doc(user.id, user.username, user.full_name, Role(role))
        new_doc["role"] = role
        await users().insert_one(new_doc)
        log.info("new user registered: %d @%s", user.id, user.username)
        return True

    if doc.get("is_banned") and not cfg.is_owner(user.id):
        if update.message:
            await update.message.reply_text(
                "🚫 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ʜᴀs ʙᴇᴇɴ sᴜsᴘᴇɴᴅᴇᴅ.\n"
                "ᴄᴏɴᴛᴀᴄᴛ sᴜᴘᴘᴏʀᴛ: @song_assistant"
            )
        return False

    await users().update_one(
        {"user_id": user.id},
        {"$set": {"last_seen": datetime.utcnow(), "username": user.username, "full_name": user.full_name}},
    )
    return True


def require_admin(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not cfg.is_admin(user.id):
            if update.message:
                await update.message.reply_text("⛔ ᴀᴅᴍɪɴ ᴏɴʟʏ.")
            elif update.callback_query:
                await update.callback_query.answer("⛔ admin only.", show_alert=True)
            return
        return await func(update, context)
    return wrapper


def require_premium(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        if cfg.is_admin(user.id):
            return await func(update, context)
        doc = await users().find_one({"user_id": user.id})
        if not doc or doc.get("role") not in ("premium", "admin", "owner"):
            if update.callback_query:
                await update.callback_query.answer(
                    "💎 ᴛʜɪs ɪs ᴀ ᴘʀᴇᴍɪᴜᴍ ꜰᴇᴀᴛᴜʀᴇ.", show_alert=True
                )
            elif update.message:
                await update.message.reply_text(
                    "💎 ᴛʜɪs ꜰᴇᴀᴛᴜʀᴇ ʀᴇǫᴜɪʀᴇs ᴘʀᴇᴍɪᴜᴍ.\n"
                    "ᴜsᴇ /premium ᴛᴏ ᴜᴘɢʀᴀᴅᴇ."
                )
            return
        return await func(update, context)
    return wrapper
