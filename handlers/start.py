"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — start & menu handler
entry point, deep-link resolver, main navigation
"""

from __future__ import annotations
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from middlewares import auth_middleware, check_membership, rate_limit_middleware
from services import UserService, FileService, ShareService
from utils import (
    main_menu, with_footer, format_size, format_dt,
    channel_log, back_btn, time_left, premium_menu, search_filters,
    safe_edit, BOT_NAME, btn, row, build, url_btn
)
from config import cfg

log = logging.getLogger(__name__)

WELCOME = (
    "╔══════════════════════════════════╗\n"
    "║  🔒 <b>sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ</b>  ║\n"
    "║    ʏᴏᴜʀ ᴘʀɪᴠᴀᴛᴇ ᴄʟᴏᴜᴅ ᴠᴀᴜʟᴛ      ║\n"
    "╚══════════════════════════════════╝\n\n"
    "ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ, <b>{name}</b> 👋\n\n"
    "🟢  sᴛᴏʀᴇ & ᴏʀɢᴀɴɪᴢᴇ ᴀɴʏ ꜰɪʟᴇ\n"
    "🔵  ꜰᴜʟʟ-ᴛᴇxᴛ ꜰɪʟᴇ sᴇᴀʀᴄʜ\n"
    "🔴  ᴇɴᴄʀʏᴘᴛᴇᴅ ᴘʀɪᴠᴀᴛᴇ ᴠᴀᴜʟᴛ\n"
    "🟣  sᴇᴄᴜʀᴇ sʜᴀʀᴇ ʟɪɴᴋs\n"
    "💎  ᴘʀᴇᴍɪᴜᴍ — ᴜɴʟɪᴍɪᴛᴇᴅ sᴛᴏʀᴀɢᴇ\n\n"
    "ᴄʜᴏᴏsᴇ ᴀɴ ᴏᴘᴛɪᴏɴ ʙᴇʟᴏᴡ ↓"
)

# ── loading animation frames ──────────────────────────────────────────────────

_FRAMES = [
    ("⚡", "ʙᴏᴏᴛɪɴɢ sᴇᴄᴜʀᴇ ᴠᴀᴜʟᴛ",    10),
    ("🔍", "sᴄᴀɴɴɪɴɢ ꜰɪʟᴇ sʏsᴛᴇᴍ",    25),
    ("🔐", "ɪɴɪᴛɪᴀʟɪᴢɪɴɢ ᴇɴᴄʀʏᴘᴛɪᴏɴ", 45),
    ("📡", "ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴅᴀᴛᴀʙᴀsᴇ",      65),
    ("🛡", "sᴇᴄᴜʀɪɴɢ sᴇssɪᴏɴ",          85),
    ("✅", "ʀᴇᴀᴅʏ!",                    100),
]


def _progress_bar(pct: int) -> str:
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)
    return f"[{bar}] {pct}%"


async def _show_loading(message) -> None:
    """Animate a loading progress bar through all frames."""
    for icon, label, pct in _FRAMES:
        text = f"{icon}  <b>{label}…</b>\n\n<code>{_progress_bar(pct)}</code>"
        try:
            await message.edit_text(text, parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(0.35)


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

    # loading animation
    loading_msg = await update.message.reply_text(
        f"⚡  <b>ʙᴏᴏᴛɪɴɢ sᴇᴄᴜʀᴇ ᴠᴀᴜʟᴛ…</b>\n\n<code>{_progress_bar(0)}</code>",
        parse_mode="HTML",
    )
    await _show_loading(loading_msg)

    is_premium = await UserService.is_premium(user.id)
    is_admin = cfg.is_admin(user.id)

    text = with_footer(WELCOME.format(name=user.first_name))
    markup = main_menu(is_premium=is_premium, is_admin=is_admin)

    try:
        await loading_msg.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
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
        f"└ sʜᴀʀᴇᴅ ᴠɪᴀ sᴇᴄʀᴇᴛ ꜰɪʟᴇ sᴛᴏʀᴀɢᴇ ʙᴏᴛ"
    )

    storage_channel = file_doc.get("storage_channel_id") or cfg.STORAGE_CHANNEL_ID

    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=storage_channel,
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
        await safe_edit(query, text, reply_markup=markup, parse_mode="HTML")

    elif action == "stats":
        await _show_my_stats(query, context)

    elif action == "help":
        await _show_help(query)

    elif action == "about":
        await _show_about(query)

    elif action == "premium":
        is_premium = await UserService.is_premium(query.from_user.id)
        await safe_edit(
            query,
            with_footer(_premium_text(is_premium)),
            reply_markup=premium_menu(has_premium=is_premium),
            parse_mode="HTML",
        )

    elif action in ("files", "folders", "search", "vault", "links", "favorites"):
        if action in ("files", "folders"):
            from handlers.folder import _show_folder
            await _show_folder(query, context, query.from_user.id, None, 0)

        elif action == "search":
            context.user_data["awaiting_search"] = True
            await safe_edit(
                query,
                "🔍  <b>sᴇᴀʀᴄʜ ʏᴏᴜʀ ꜰɪʟᴇs</b>\n\nᴛʏᴘᴇ ᴀ ꜰɪʟᴇ ɴᴀᴍᴇ, ᴛᴀɢ, ᴏʀ ᴋᴇʏᴡᴏʀᴅ:",
                reply_markup=search_filters(),
                parse_mode="HTML",
            )

        elif action == "vault":
            from handlers.vault import _show_vault_entry
            await _show_vault_entry(update, context)

        elif action == "links":
            from handlers.share import _show_links_list
            await _show_links_list(query, context, 0)

        elif action == "favorites":
            from handlers.favorites import _show_favorites
            await _show_favorites(update, context, query.from_user.id, 0)


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

    if limit == 0:
        pct = 0
        bar = "░" * 10
        limit_str = "∞ ᴜɴʟɪᴍɪᴛᴇᴅ"
    else:
        pct = min(100, round(storage / limit * 100)) if limit else 0
        bar = ("█" * (pct // 10)) + ("░" * (10 - pct // 10))
        limit_str = format_size(limit)

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
        f"├ sᴛᴏʀᴀɢᴇ: {format_size(storage)} / {limit_str}\n"
        f"├ ᴜsᴀɢᴇ:   [{bar}] {'∞' if limit == 0 else f'{pct}%'}\n"
        f"└ ᴊᴏɪɴᴇᴅ:  {format_dt(user['joined_at'])}"
    )
    await safe_edit(query, with_footer(text), reply_markup=back_btn("menu:start"), parse_mode="HTML")


def _premium_text(is_premium: bool) -> str:
    if is_premium:
        return (
            "💎  <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴇ</b>\n\n"
            "✅ ᴜɴʟɪᴍɪᴛᴇᴅ sᴛᴏʀᴀɢᴇ\n"
            "✅ 2 ɢʙ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ\n"
            "✅ ᴀᴅᴠᴀɴᴄᴇᴅ sᴇᴀʀᴄʜ ꜰɪʟᴛᴇʀs\n"
            "✅ ʙᴜʟᴋ ᴏᴘᴇʀᴀᴛɪᴏɴs\n"
            "✅ ᴘʀɪᴏʀɪᴛʏ sᴜᴘᴘᴏʀᴛ"
        )
    return (
        "💎  <b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ</b>\n\n"
        "<b>🆓 ꜰʀᴇᴇ ᴘʟᴀɴ</b>\n"
        "• 500 ᴍʙ sᴛᴏʀᴀɢᴇ\n"
        "• 20 ᴍʙ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ\n\n"
        "<b>👑 ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴ</b>\n"
        "• ∞ ᴜɴʟɪᴍɪᴛᴇᴅ sᴛᴏʀᴀɢᴇ\n"
        "• 2 ɢʙ ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ\n"
        "• ᴀʟʟ ꜰᴇᴀᴛᴜʀᴇs ᴜɴʟᴏᴄᴋᴇᴅ\n\n"
        "<b>ᴘʀɪᴄɪɴɢ</b>\n"
        "• 👑 ʏᴇᴀʀʟʏ: <b>₹39 / ʏᴇᴀʀ</b>  —  ᴜɴʟɪᴍɪᴛᴇᴅ"
    )


async def _show_help(query) -> None:
    is_premium = await UserService.is_premium(query.from_user.id)
    premium_note = "💎 <i>ᴘʀᴇᴍɪᴜᴍ</i>" if is_premium else "🆓 <i>ꜰʀᴇᴇ — /premium ᴜᴘɢʀᴀᴅᴇ</i>"

    text = (
        f"🔒  <b>sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ</b>\n"
        f"<i>ᴄᴏᴍᴍᴀɴᴅs ɢᴜɪᴅᴇ</i>  ·  {premium_note}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📁  <b>/start</b>  —  ᴍᴀɪɴ ᴍᴇɴᴜ\n"
        "📤  <b>/upload</b>  —  ᴜᴘʟᴏᴀᴅ ᴀ ꜰɪʟᴇ\n"
        "🔍  <b>/search</b>  —  sᴇᴀʀᴄʜ ꜰɪʟᴇs\n"
        "🔐  <b>/vault</b>  —  ᴇɴᴄʀʏᴘᴛᴇᴅ ᴠᴀᴜʟᴛ\n"
        "💎  <b>/premium</b>  —  ᴘʀᴇᴍɪᴜᴍ ᴘʟᴀɴs\n"
        "📊  <b>/stats</b>  —  sᴛᴏʀᴀɢᴇ ɪɴꜰᴏ\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡  sᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ ᴅɪʀᴇᴄᴛʟʏ ᴛᴏ ᴜᴘʟᴏᴀᴅ\n"
        "🏷  ᴀᴅᴅ <code>#ᴛᴀɢ</code> ɪɴ ᴄᴀᴘᴛɪᴏɴ ᴛᴏ ᴀᴜᴛᴏ-ᴛᴀɢ"
    )

    markup = build(
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start")),
        row(
            url_btn("👨‍💻  @its_me_secret",    "https://t.me/its_me_secret"),
            url_btn("🆘  @song_assistant", "https://t.me/song_assistant"),
        ),
    )
    await safe_edit(query, with_footer(text), reply_markup=markup, parse_mode="HTML")


async def _show_about(query) -> None:
    text = (
        "🔒  <b>sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ</b>\n\n"
        "ᴘʀᴇᴍɪᴜᴍ ᴛᴇʟᴇɢʀᴀᴍ ꜰɪʟᴇ sᴛᴏʀᴀɢᴇ &\n"
        "ᴍᴀɴᴀɢᴇᴍᴇɴᴛ ꜰᴏʀ ᴇᴠᴇʀʏᴏɴᴇ.\n\n"
        "• ᴇɴᴄʀʏᴘᴛᴇᴅ ᴠᴀᴜʟᴛ sᴛᴏʀᴀɢᴇ\n"
        "• ᴍᴜʟᴛɪ-ᴄʜᴀɴɴᴇʟ ᴅɪsᴛʀɪʙᴜᴛᴇᴅ ʙᴀᴄᴋᴜᴘs\n"
        "• ᴄᴅɴ-sᴛʏʟᴇ sᴇᴄᴜʀᴇ sʜᴀʀɪɴɢ\n"
        "• ᴀɪ-ᴘᴏᴡᴇʀᴇᴅ ᴀssɪsᴛᴀɴᴄᴇ\n"
        "• ᴘʀᴇᴍɪᴜᴍ ᴜɴʟɪᴍɪᴛᴇᴅ sᴛᴏʀᴀɢᴇ\n\n"
        "ᴠᴇʀsɪᴏɴ: 3.0.0  ·  ᴘʏᴛʜᴏɴ · ᴍᴏɴɢᴏᴅʙ"
    )
    markup = build(
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start")),
        row(
            url_btn("👨‍💻  @its_me_secret",    "https://t.me/its_me_secret"),
            url_btn("🆘  @song_assistant", "https://t.me/song_assistant"),
        ),
    )
    await safe_edit(query, with_footer(text), reply_markup=markup, parse_mode="HTML")


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
        await safe_edit(query, text, reply_markup=markup, parse_mode="HTML")
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
