"""
vault bot — authentication middleware
ensures user exists in db, checks ban status, updates last_seen with caching
"""

from __future__ import annotations
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from cachetools import TTLCache
from database import users, user_doc, Role
from config import cfg

log = logging.getLogger(__name__)

# Cache user documents in memory for 5 minutes to avoid database reads on every message
_user_cache: TTLCache[int, dict] = TTLCache(maxsize=10000, ttl=300)

# Throttle last_seen writes to once every 5 minutes per user
_last_seen_updates: TTLCache[int, float] = TTLCache(maxsize=10000, ttl=300)


def invalidate_user_cache(user_id: int) -> None:
    """Invalidate cache for a specific user. Called when roles/ban status changes."""
    _user_cache.pop(user_id, None)
    _last_seen_updates.pop(user_id, None)


async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    doc = _user_cache.get(user.id)

    if doc is None:
        doc = await users().find_one({"user_id": user.id})

        if doc is None:
            role = Role.OWNER.value if cfg.is_owner(user.id) else (
                Role.ADMIN.value if cfg.is_admin(user.id) else Role.USER.value
            )
            new_doc = user_doc(user.id, user.username, user.full_name, Role(role))
            new_doc["role"] = role
            await users().insert_one(new_doc)
            _user_cache[user.id] = new_doc
            log.info("new user registered: %d @%s", user.id, user.username)
            return True
        else:
            _user_cache[user.id] = doc

    if doc.get("is_banned") and not cfg.is_owner(user.id):
        if update.message:
            await update.message.reply_text(
                "🚫 ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ʜᴀs ʙᴇᴇɴ sᴜsᴘᴇɴᴅᴇᴅ.\n"
                "CNTACT sᴜᴘᴘᴏʀᴛ: @its_Xyron"
            )
        return False

    # Check if last_seen update is throttled
    now_ts = datetime.utcnow().timestamp()
    if user.id not in _last_seen_updates:
        await users().update_one(
            {"user_id": user.id},
            {"$set": {"last_seen": datetime.utcnow(), "username": user.username, "full_name": user.full_name}},
        )
        _last_seen_updates[user.id] = now_ts
        # Update cache as well
        doc["last_seen"] = datetime.utcnow()
        doc["username"] = user.username
        doc["full_name"] = user.full_name
        _user_cache[user.id] = doc

    return True


def require_admin(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user or not cfg.is_admin(user.id, context.bot.id):
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
        if cfg.is_admin(user.id, context.bot.id):
            return await func(update, context)

        # Use cache to check role
        doc = _user_cache.get(user.id)
        if doc is None:
            doc = await users().find_one({"user_id": user.id})
            if doc:
                _user_cache[user.id] = doc

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
