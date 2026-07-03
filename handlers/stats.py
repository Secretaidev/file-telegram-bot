"""
vault bot — stats & analytics handler
per-user usage analytics, category breakdown, activity graph
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from middlewares import auth_middleware
from services import UserService, FileService, SubscriptionService
from utils import with_footer, format_size, format_dt, time_left, back_btn, btn, row, build
from config import cfg

log = logging.getLogger(__name__)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    await _show_user_stats(update, context, from_message=True)


async def cbq_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1] if len(parts) > 1 else None
    user_id = q.from_user.id

    if action == "optimize_req":
        await q.answer()
        dups = await FileService.find_duplicates(user_id)
        total_dups = 0
        total_size = 0
        for group in dups:
            single_size = group["docs"][0]["file_size"]
            total_size += group["total_size"] - single_size
            total_dups += group["count"] - 1

        if total_dups == 0:
            text = (
                "🧹  <b>sᴘᴀᴄᴇ ᴏᴘᴛɪᴍɪᴢᴇʀ</b>\n\n"
                "🎉 <b>ɴᴏ ᴅᴜᴘʟɪᴄᴀᴛᴇs ꜰᴏᴜɴᴅ!</b>\n\n"
                "ʏᴏᴜʀ sᴛᴏʀᴀɢᴇ ɪs ᴀʟʀᴇᴀᴅʏ fully optimized."
            )
            markup = build(row(btn("◀️  ʙᴀᴄᴋ", "stats", "primary")))
        else:
            text = (
                "🧹  <b>sᴘᴀᴄᴇ ᴏᴘᴛɪᴍɪᴢᴇʀ</b>\n\n"
                f"• ᴅᴜᴘʟɪᴄᴀᴛᴇ ꜰɪʟᴇs: <b>{total_dups}</b>\n"
                f"• ʀᴇᴄʟᴀɪᴍᴀʙʟᴇ sᴘᴀᴄᴇ: <b>{format_size(total_size)}</b>\n\n"
                "Tapping the button below will keep one copy of each file and delete the duplicate copies."
            )
            markup = build(
                row(btn("🧹  ᴄʟᴇᴀɴ ᴅᴜᴘʟɪᴄᴀᴛᴇs", "stats:optimize_run", "success")),
                row(btn("◀️  ʙᴀᴄᴋ", "stats", "primary"))
            )
        await q.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")

    elif action == "optimize_run":
        files_deleted, space_saved = await FileService.clean_duplicates(user_id)
        await q.answer(f"🧹 Cleaned {files_deleted} duplicates!")
        text = (
            "🧹  <b>sᴘᴀᴄᴇ ᴏᴘᴛɪᴍɪᴢᴇʀ</b>\n\n"
            "✅  <b>sᴛᴏʀᴀɢᴇ ᴏᴘᴛɪᴍɪᴢᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ!</b>\n\n"
            f"• ᴅᴜᴘʟɪᴄᴀᴛᴇs ᴅᴇʟᴇᴛᴇᴅ: <b>{files_deleted}</b>\n"
            f"• sᴘᴀᴄᴇ ʀᴇᴄʟᴀɪᴍᴇᴅ: <b>{format_size(space_saved)}</b>"
        )
        markup = build(row(btn("◀️  ʙᴀᴄᴋ", "stats", "primary")))
        await q.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")

    else:
        await q.answer()
        await _show_user_stats(update, context)


async def _show_user_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    from_message: bool = False,
) -> None:
    user = update.effective_user
    user_doc = await UserService.get(user.id)
    if not user_doc:
        return

    is_premium = user_doc.get("role") in ("premium", "admin", "owner")
    storage_used = user_doc.get("storage_used", 0)
    storage_limit = cfg.PREMIUM_STORAGE_LIMIT if is_premium else cfg.FREE_STORAGE_LIMIT
    upload_limit = cfg.PREMIUM_UPLOAD_LIMIT if is_premium else cfg.FREE_UPLOAD_LIMIT
    pct = min(100, round(storage_used / storage_limit * 100)) if storage_limit else 0

    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)

    role_badge = {
        "owner":   "👑 ᴏᴡɴᴇʀ",
        "admin":   "⚙️ ᴀᴅᴍɪɴ",
        "premium": "💎 ᴘʀᴇᴍɪᴜᴍ",
        "user":    "🆓 ꜰʀᴇᴇ",
        "banned":  "🚫 ʙᴀɴɴᴇᴅ",
    }.get(user_doc.get("role", "user"), "🆓 ꜰʀᴇᴇ")

    _, total_files = await FileService.list_user_files(user.id, limit=1)
    _, vault_count = await FileService.list_user_files(user.id, is_vault=True, limit=1)
    fav_count = len(user_doc.get("favorites", []))
    recent_count = len(user_doc.get("recent", []))

    cat_breakdown = await _user_category_breakdown(user.id)
    cat_lines = "  " + " · ".join(
        f"{_cat_emoji(k)} {v}" for k, v in cat_breakdown.items()
    ) if cat_breakdown else "  —"

    sub = await SubscriptionService.get_active(user.id) if is_premium else None
    sub_line = (
        f"└ ᴇxᴘɪʀᴇs: {time_left(sub['expires_at'])}"
        if sub else ""
    )

    text = (
        f"📊  <b>ᴍʏ sᴛᴀᴛs</b>\n\n"

        f"┌ <b>ᴀᴄᴄᴏᴜɴᴛ</b>\n"
        f"├ ɴᴀᴍᴇ:   {user.full_name}\n"
        f"├ ᴘʟᴀɴ:   {role_badge}\n"
        f"├ ᴊᴏɪɴᴇᴅ: {format_dt(user_doc['joined_at'])}\n"
        f"└ sᴇᴇɴ:   {format_dt(user_doc['last_seen'])}\n\n"

        f"┌ <b>sᴛᴏʀᴀɢᴇ</b>\n"
        f"├ ᴜsᴇᴅ:    {format_size(storage_used)} / {format_size(storage_limit)}\n"
        f"├ ᴜsᴀɢᴇ:   [{bar}] {pct}%\n"
        f"└ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ: {format_size(upload_limit)}\n\n"

        f"┌ <b>ꜰɪʟᴇs</b>\n"
        f"├ ᴛᴏᴛᴀʟ:     {total_files}\n"
        f"├ ᴠᴀᴜʟᴛ:     {vault_count}\n"
        f"├ ꜰᴀᴠᴏʀɪᴛᴇs: {fav_count}\n"
        f"├ ʀᴇᴄᴇɴᴛ:    {recent_count}\n"
        f"└ ᴄᴀᴛᴇɢᴏʀɪᴇs:\n{cat_lines}\n"
    )

    if sub_line:
        text += f"\n┌ <b>ᴘʀᴇᴍɪᴜᴍ</b>\n{sub_line}"

    markup = build(
        row(btn("🧹  sᴘᴀᴄᴇ ᴏᴘᴛɪᴍɪᴢᴇʀ", "stats:optimize_req", "success")),
        row(btn("⭐  ꜰᴀᴠᴏʀɪᴛᴇs", "favs:list:0"), btn("⏱  ʀᴇᴄᴇɴᴛ", "favs:recent")),
        row(btn("💎  ᴘʀᴇᴍɪᴜᴍ", "menu:premium"), btn("◀️  ʙᴀᴄᴋ", "menu:start")),
    )

    if from_message:
        await update.message.reply_text(with_footer(text), reply_markup=markup, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")


async def _user_category_breakdown(user_id: int) -> dict:
    from database import files
    pipeline = [
        {"$match": {"owner_id": user_id, "is_deleted": False}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    result = await files().aggregate(pipeline).to_list(5)
    return {r["_id"]: r["count"] for r in result}


def _cat_emoji(cat: str) -> str:
    return {
        "video":    "🎬",
        "audio":    "🎵",
        "photo":    "🖼",
        "document": "📄",
        "archive":  "📦",
        "other":    "📎",
    }.get(cat, "📎")


def get_handlers():
    return [
        CommandHandler("stats", cmd_stats),
        CallbackQueryHandler(cbq_stats, pattern=r"^stats:"),
    ]
