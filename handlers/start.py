"""
vault bot — start & menu handler
entry point, deep-link resolver, main navigation
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from middlewares import auth_middleware, check_membership, rate_limit_middleware
from services import UserService, FileService, ShareService
from utils import (
    main_menu, with_footer, format_size, format_dt,
    channel_log, back_btn, time_left, premium_menu
)
from config import cfg

log = logging.getLogger(__name__)

WELCOME = (
    "╔══════════════════════════════╗\n"
    "║      📦  <b>ᴠᴀᴜʟᴛ ʙᴏᴛ</b>           ║\n"
    "║  ʏᴏᴜʀ ᴘʀɪᴠᴀᴛᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴅʀɪᴠᴇ  ║\n"
    "╚══════════════════════════════╝\n\n"
    "ᴡᴇʟᴄᴏᴍᴇ, <b>{name}</b>!\n\n"
    "• 📁  sᴛᴏʀᴇ & ᴏʀɢᴀɴɪᴢᴇ ᴀɴʏ ꜰɪʟᴇ\n"
    "• 🔍  ꜰᴜʟʟ-ᴛᴇxᴛ sᴇᴀʀᴄʜ\n"
    "• 🔐  ᴇɴᴄʀʏᴘᴛᴇᴅ ᴘʀɪᴠᴀᴛᴇ ᴠᴀᴜʟᴛ\n"
    "• 🔗  sᴇᴄᴜʀᴇ sʜᴀʀᴇ ʟɪɴᴋs\n"
    "• 💎  ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs ᴀᴠᴀɪʟᴀʙʟᴇ\n\n"
    "ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ ↓"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    if not await rate_limit_middleware(update, context):
        return
    if not await check_membership(update, context):
        return

    user = update.effective_user
    args = context.args or []

    if args:
        payload = args[0]
        if payload.startswith("dl_"):
            await _handle_deep_link(update, context, payload[3:])
            return

    is_premium = await UserService.is_premium(user.id)
    is_admin = cfg.is_admin(user.id)

    text = with_footer(WELCOME.format(name=user.first_name))
    markup = main_menu(is_premium=is_premium, is_admin=is_admin)

    await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")

    await channel_log(
        context.bot, "join", user.id, user.username,
        details={"name": user.full_name},
    )


async def _handle_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, token: str) -> None:
    user = update.effective_user
    link, reason = await ShareService.resolve_token(token)

    if not link:
        await update.message.reply_text(
            f"❌ ᴛʜɪs ʟɪɴᴋ ɪs ɴᴏ ʟᴏɴɢᴇʀ ᴠᴀʟɪᴅ.\n<i>{reason}</i>",
            parse_mode="HTML",
        )
        return

    if link.get("password"):
        context.user_data["pending_link_token"] = token
        await update.message.reply_text(
            "🔒 ᴛʜɪs ʟɪɴᴋ ɪs ᴘᴀssᴡᴏʀᴅ ᴘʀᴏᴛᴇᴄᴛᴇᴅ.\n"
            "ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴘᴀssᴡᴏʀᴅ:",
            reply_markup=back_btn("menu:start"),
        )
        return

    await _deliver_shared_file(update, context, link)


async def _deliver_shared_file(update: Update, context: ContextTypes.DEFAULT_TYPE, link: dict) -> None:
    from services import FileService
    from utils import category_icon

    file_doc = await FileService.get_by_id(link["file_id"])
    if not file_doc:
        await update.message.reply_text("❌ ꜰɪʟᴇ ɴᴏ ʟᴏɴɢᴇʀ ᴀᴠᴀɪʟᴀʙʟᴇ.")
        return

    icon = category_icon(file_doc.get("category", "other"))
    caption = (
        f"{icon}  <b>{file_doc['file_name']}</b>\n"
        f"├ sɪᴢᴇ: {format_size(file_doc.get('file_size', 0))}\n"
        f"└ sʜᴀʀᴇᴅ ꜰɪʟᴇ ᴠɪᴀ ᴠᴀᴜʟᴛ ʙᴏᴛ"
    )

    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=cfg.STORAGE_CHANNEL_ID,
            message_id=file_doc["message_id"],
            caption=with_footer(caption),
            parse_mode="HTML",
        )
    except Exception as e:
        log.error("failed to deliver shared file: %s", e)
        await update.message.reply_text("❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ᴅᴇʟɪᴠᴇʀ ꜰɪʟᴇ. ᴛʀʏ ᴀɢᴀɪɴ.")
        return

    await ShareService.record_access(str(link["_id"]), downloaded=True)
    await ShareService.deactivate_if_one_time(link)
    await FileService.increment_downloads(link["file_id"])

    await channel_log(
        context.bot, "download", update.effective_user.id,
        update.effective_user.username,
        details={"file": file_doc["file_name"], "token": link["token"]},
    )


# ── menu navigation ───────────────────────────────────────────────────────────

async def cbq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    if action == "start":
        user = update.effective_user
        is_premium = await UserService.is_premium(user.id)
        is_admin = cfg.is_admin(user.id)
        text = with_footer(WELCOME.format(name=user.first_name))
        markup = main_menu(is_premium=is_premium, is_admin=is_admin)
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")

    elif action == "stats":
        await _show_my_stats(query, context)

    elif action == "help":
        await _show_help(query)

    elif action == "about":
        await _show_about(query)

    elif action == "premium":
        is_premium = await UserService.is_premium(query.from_user.id)
        await query.edit_message_text(
            with_footer(_premium_text(is_premium)),
            reply_markup=premium_menu(has_premium=is_premium),
            parse_mode="HTML",
        )

    elif action in ("files", "folders", "search", "vault", "links", "favorites"):
        context.user_data["nav_section"] = action
        await query.answer(f"ᴏᴘᴇɴɪɴɢ {action}…")


async def _show_my_stats(query, context) -> None:
    user_id = query.from_user.id
    user = await UserService.get(user_id)
    if not user:
        await query.answer("user not found", show_alert=True)
        return

    from services import FileService
    _, total_files = await FileService.list_user_files(user_id, skip=0, limit=1)
    storage = user.get("storage_used", 0)
    is_premium = user.get("role") in ("premium", "admin", "owner")
    limit = cfg.PREMIUM_STORAGE_LIMIT if is_premium else cfg.FREE_STORAGE_LIMIT
    pct = min(100, round(storage / limit * 100)) if limit else 0
    bar = ("█" * (pct // 10)) + ("░" * (10 - pct // 10))

    role_badge = {
        "owner":   "👑 ᴏᴡɴᴇʀ",
        "admin":   "⚙️ ᴀᴅᴍɪɴ",
        "premium": "💎 ᴘʀᴇᴍɪᴜᴍ",
        "user":    "🆓 ꜰʀᴇᴇ",
    }.get(user.get("role", "user"), "🆓 ꜰʀᴇᴇ")

    text = (
        f"📊  <b>ᴍʏ sᴛᴀᴛs</b>\n\n"
        f"├ ᴘʟᴀɴ:    {role_badge}\n"
        f"├ ꜰɪʟᴇs:   {total_files}\n"
        f"├ sᴛᴏʀᴀɢᴇ: {format_size(storage)} / {format_size(limit)}\n"
        f"├ ᴜsᴀɢᴇ:   [{bar}] {pct}%\n"
        f"└ ᴊᴏɪɴᴇᴅ:  {format_dt(user['joined_at'])}"
    )
    await query.edit_message_text(with_footer(text), reply_markup=back_btn("menu:start"), parse_mode="HTML")


def _premium_text(is_premium: bool) -> str:
    if is_premium:
        return (
            "💎  <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴇ</b>\n\n"
            "✅ ᴜɴʟɪᴍɪᴛᴇᴅ ᴠᴀᴜʟᴛ ᴀᴄᴄᴇss\n"
            "✅ 2 ɢʙ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ\n"
            "✅ 10 ɢʙ sᴛᴏʀᴀɢᴇ\n"
            "✅ ᴀᴅᴠᴀɴᴄᴇᴅ sᴇᴀʀᴄʜ ꜰɪʟᴛᴇʀs\n"
            "✅ ʙᴜʟᴋ ᴏᴘᴇʀᴀᴛɪᴏɴs\n"
            "✅ ᴘʀɪᴏʀɪᴛʏ sᴜᴘᴘᴏʀᴛ"
        )
    return (
        "💎  <b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ</b>\n\n"
        "<b>ꜰʀᴇᴇ ᴘʟᴀɴ</b>\n"
        "• 500 ᴍʙ sᴛᴏʀᴀɢᴇ\n"
        "• 20 ᴍʙ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ\n"
        "• ʙᴀsɪᴄ sᴇᴀʀᴄʜ\n\n"
        "<b>💎 ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ</b>\n"
        "• 10 ɢʙ sᴛᴏʀᴀɢᴇ\n"
        "• 2 ɢʙ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ\n"
        "• ᴀʟʟ ꜰᴇᴀᴛᴜʀᴇs ᴜɴʟᴏᴄᴋᴇᴅ\n"
        "• ᴘʀɪᴏʀɪᴛʏ sᴜᴘᴘᴏʀᴛ\n\n"
        "<b>ᴘʀɪᴄɪɴɢ</b>\n"
        "• ᴍᴏɴᴛʜʟʏ: ₹99/ᴍᴏɴᴛʜ\n"
        "• ʏᴇᴀʀʟʏ:  ₹799/ʏᴇᴀʀ (save 32%)"
    )


async def _show_help(query) -> None:
    text = (
        "❓  <b>ʜᴇʟᴘ & ᴄᴏᴍᴍᴀɴᴅs</b>\n\n"
        "/start — ᴍᴀɪɴ ᴍᴇɴᴜ\n"
        "/upload — ᴜᴘʟᴏᴀᴅ ᴀ ꜰɪʟᴇ\n"
        "/search — sᴇᴀʀᴄʜ ʏᴏᴜʀ ꜰɪʟᴇs\n"
        "/vault — ᴏᴘᴇɴ ᴇɴᴄʀʏᴘᴛᴇᴅ ᴠᴀᴜʟᴛ\n"
        "/premium — ᴜᴘɢʀᴀᴅᴇ ᴘʟᴀɴ\n"
        "/stats — ᴍʏ ᴀᴄᴄᴏᴜɴᴛ ɪɴꜰᴏ\n\n"
        "ᴛᴏ ᴜᴘʟᴏᴀᴅ ᴀ ꜰɪʟᴇ, ᴊᴜsᴛ sᴇɴᴅ ɪᴛ ᴛᴏ ᴛʜᴇ ʙᴏᴛ ᴅɪʀᴇᴄᴛʟʏ.\n"
        "ᴛᴏ sᴇᴀʀᴄʜ, sᴇɴᴅ ᴀɴʏ ᴛᴇxᴛ ᴏʀ ᴜsᴇ /search."
    )
    await query.edit_message_text(with_footer(text), reply_markup=back_btn("menu:start"), parse_mode="HTML")


async def _show_about(query) -> None:
    text = (
        "ℹ️  <b>ᴀʙᴏᴜᴛ ᴠᴀᴜʟᴛ ʙᴏᴛ</b>\n\n"
        "ᴀ ᴘʀᴏᴅᴜᴄᴛɪᴏɴ-ɢʀᴀᴅᴇ ᴛᴇʟᴇɢʀᴀᴍ ꜰɪʟᴇ\n"
        "sᴛᴏʀᴀɢᴇ & ᴍᴀɴᴀɢᴇᴍᴇɴᴛ sʏsᴛᴇᴍ.\n\n"
        "• ꜰɪʟᴇ sᴛᴏʀᴀɢᴇ ᴇɴɢɪɴᴇ\n"
        "• ᴇɴᴄʀʏᴘᴛᴇᴅ ᴘʀɪᴠᴀᴛᴇ ᴠᴀᴜʟᴛ\n"
        "• ᴄᴅɴ-sᴛʏʟᴇ sʜᴀʀɪɴɢ\n"
        "• ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴs\n\n"
        "ᴠᴇʀsɪᴏɴ: 2.0.0\n"
        "ᴛᴇᴄʜ: ᴘʏᴛʜᴏɴ · ᴍᴏɴɢᴏᴅʙ · ᴛᴇʟᴇɢʀᴀᴍ"
    )
    await query.edit_message_text(with_footer(text), reply_markup=back_btn("menu:start"), parse_mode="HTML")


async def cbq_check_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    passed = await check_membership(update, context)
    if passed:
        await query.answer("✅ ᴛʜᴀɴᴋs ꜰᴏʀ ᴊᴏɪɴɪɴɢ!", show_alert=False)
        user = update.effective_user
        is_premium = await UserService.is_premium(user.id)
        is_admin = cfg.is_admin(user.id)
        text = with_footer(WELCOME.format(name=user.first_name))
        markup = main_menu(is_premium=is_premium, is_admin=is_admin)
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await query.answer("❌ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ.", show_alert=True)


async def cbq_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()


async def cbq_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.message.delete()


def get_handlers():
    return [
        CommandHandler("start", cmd_start),
        CallbackQueryHandler(cbq_menu, pattern=r"^menu:"),
        CallbackQueryHandler(cbq_check_joined, pattern=r"^check:joined$"),
        CallbackQueryHandler(cbq_noop, pattern=r"^noop$"),
        CallbackQueryHandler(cbq_close, pattern=r"^close$"),
    ]
