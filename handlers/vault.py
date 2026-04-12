"""
vault bot — vault handler
pin setup, unlock, lock, vault file listing
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)
from middlewares import auth_middleware, check_membership, rate_limit_middleware
from services import VaultService, FileService, UserService
from utils import (
    vault_menu, vault_unlock, file_actions, with_footer,
    format_size, category_icon, back_btn, channel_log, btn, row, build
)
from config import cfg

log = logging.getLogger(__name__)


async def cmd_vault(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    if not await check_membership(update, context):
        return
    await _show_vault_entry(update, context)


async def _show_vault_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    has_pin = await VaultService.has_pin(user_id)

    if not has_pin:
        context.user_data["vault_state"] = "setup_pin"
        text = (
            "🔐  <b>sᴇᴛᴜᴘ ᴠᴀᴜʟᴛ ᴘɪɴ</b>\n\n"
            "ʏᴏᴜʀ ᴠᴀᴜʟᴛ ɪs ɴᴏᴛ ᴄᴏɴꜰɪɢᴜʀᴇᴅ ʏᴇᴛ.\n\n"
            "sᴇɴᴅ ᴀ 4-6 ᴅɪɢɪᴛ ᴘɪɴ ᴛᴏ sᴇᴄᴜʀᴇ ʏᴏᴜʀ ᴠᴀᴜʟᴛ:"
        )
        msg = update.message or update.callback_query.message
        fn = msg.reply_text if update.message else update.callback_query.edit_message_text
        await fn(with_footer(text), reply_markup=back_btn("menu:start"), parse_mode="HTML")
        return

    is_unlocked = await VaultService.is_unlocked(user_id)
    if is_unlocked:
        await _show_vault_menu(update, context)
        return

    text = (
        "🔐  <b>ᴠᴀᴜʟᴛ ʟᴏᴄᴋᴇᴅ</b>\n\n"
        "ʏᴏᴜʀ ᴠᴀᴜʟᴛ ɪs sᴇᴄᴜʀᴇᴅ.\n"
        "ᴇɴᴛᴇʀ ʏᴏᴜʀ ᴘɪɴ ᴛᴏ ᴜɴʟᴏᴄᴋ:"
    )
    context.user_data["vault_state"] = "enter_pin"
    msg = update.message or update.callback_query.message
    fn = msg.reply_text if update.message else update.callback_query.edit_message_text
    await fn(with_footer(text), reply_markup=vault_unlock(), parse_mode="HTML")


async def _show_vault_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    files, total = await VaultService.list_vault_files(user_id)

    text = (
        f"🔐  <b>ᴠᴀᴜʟᴛ — ᴜɴʟᴏᴄᴋᴇᴅ</b>\n\n"
        f"├ ꜰɪʟᴇs: {total}\n"
        f"└ sᴇssɪᴏɴ ᴀᴜᴛᴏ-ʟᴏᴄᴋs ɪɴ {cfg.SESSION_TIMEOUT // 60}ᴍɪɴ"
    )
    msg = update.message or update.callback_query.message
    fn = msg.reply_text if update.message else update.callback_query.edit_message_text
    await fn(with_footer(text), reply_markup=vault_menu(), parse_mode="HTML")


async def cbq_vault(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    user_id = q.from_user.id

    if action == "enter_pin":
        await q.answer()
        context.user_data["vault_state"] = "enter_pin"
        await q.edit_message_text(
            with_footer("🔐 sᴇɴᴅ ʏᴏᴜʀ ᴘɪɴ:"),
            reply_markup=back_btn("menu:start"),
            parse_mode="HTML",
        )

    elif action == "lock":
        await q.answer()
        await VaultService.lock(user_id)
        await q.edit_message_text(
            with_footer("🔒  ᴠᴀᴜʟᴛ ʟᴏᴄᴋᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ."),
            reply_markup=back_btn("menu:start"),
            parse_mode="HTML",
        )

    elif action == "list":
        await q.answer()
        page = int(parts[2]) if len(parts) > 2 else 0
        await _show_vault_files(q, context, user_id, page)

    elif action == "upload":
        await q.answer()
        context.user_data["upload_to_vault"] = True
        await q.edit_message_text(
            with_footer("📤  sᴇɴᴅ ᴀ ꜰɪʟᴇ ᴛᴏ ᴀᴅᴅ ɪᴛ ᴛᴏ ʏᴏᴜʀ ᴠᴀᴜʟᴛ:"),
            reply_markup=back_btn("menu:vault"),
            parse_mode="HTML",
        )

    elif action == "change_pin":
        await q.answer()
        context.user_data["vault_state"] = "change_pin_old"
        await q.edit_message_text(
            with_footer("🔑  ᴇɴᴛᴇʀ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴘɪɴ:"),
            reply_markup=back_btn("menu:vault"),
            parse_mode="HTML",
        )


async def _show_vault_files(q, context, user_id: int, page: int) -> None:
    vault_files, total = await VaultService.list_vault_files(user_id, page)
    total_pages = max(1, (total + cfg.PAGE_SIZE - 1) // cfg.PAGE_SIZE)

    if not vault_files:
        await q.edit_message_text(
            with_footer("🔐  <b>ᴠᴀᴜʟᴛ ɪs ᴇᴍᴘᴛʏ</b>\n\nᴜᴘʟᴏᴀᴅ ꜰɪʟᴇs ᴛᴏ ʏᴏᴜʀ ᴠᴀᴜʟᴛ."),
            reply_markup=vault_menu(),
            parse_mode="HTML",
        )
        return

    rows = []
    for f in vault_files:
        icon = category_icon(f.get("category", "other"))
        rows.append(row(btn(f"{icon}  {f['file_name']}", f"file:view:{f['_id']}")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"vault:list:{page-1}"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"vault:list:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "menu:vault")))

    await q.edit_message_text(
        with_footer(f"🔐  <b>ᴠᴀᴜʟᴛ ꜰɪʟᴇs</b> ({total})"),
        reply_markup=build(*rows),
        parse_mode="HTML",
    )


async def handle_vault_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.get("vault_state")
    if not state:
        return

    user_id = update.effective_user.id
    pin = update.message.text.strip()

    try:
        await update.message.delete()
    except Exception:
        pass

    if state == "setup_pin":
        if not pin.isdigit() or not (4 <= len(pin) <= 6):
            await update.message.reply_text("❌ ᴘɪɴ ᴍᴜsᴛ ʙᴇ 4-6 ᴅɪɢɪᴛs. ᴛʀʏ ᴀɢᴀɪɴ:")
            return
        context.user_data["vault_new_pin"] = pin
        context.user_data["vault_state"] = "confirm_pin"
        await update.message.reply_text(
            with_footer("🔐  ᴄᴏɴꜰɪʀᴍ ʏᴏᴜʀ ᴘɪɴ:"),
            reply_markup=back_btn("menu:start"),
            parse_mode="HTML",
        )

    elif state == "confirm_pin":
        expected = context.user_data.pop("vault_new_pin", None)
        context.user_data.pop("vault_state", None)
        if pin != expected:
            await update.message.reply_text("❌ ᴘɪɴs ᴅᴏ ɴᴏᴛ ᴍᴀᴛᴄʜ. /vault ᴛᴏ ᴛʀʏ ᴀɢᴀɪɴ.")
            return
        await VaultService.set_pin(user_id, pin)
        await VaultService.create_session(user_id)
        context.user_data.pop("vault_state", None)
        await update.message.reply_text(
            with_footer("✅  ᴘɪɴ sᴇᴛ! ᴠᴀᴜʟᴛ ᴜɴʟᴏᴄᴋᴇᴅ."),
            reply_markup=vault_menu(),
            parse_mode="HTML",
        )
        await channel_log(context.bot, "vault", user_id, update.effective_user.username, details={"action": "pin_set"})

    elif state == "enter_pin":
        ok = await VaultService.verify_pin(user_id, pin)
        if ok:
            await VaultService.create_session(user_id)
            context.user_data.pop("vault_state", None)
            await update.message.reply_text(
                with_footer("🔓  ᴠᴀᴜʟᴛ ᴜɴʟᴏᴄᴋᴇᴅ."),
                reply_markup=vault_menu(),
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ ᴡʀᴏɴɢ ᴘɪɴ. ᴛʀʏ ᴀɢᴀɪɴ:")

    elif state == "change_pin_old":
        ok = await VaultService.verify_pin(user_id, pin)
        if ok:
            context.user_data["vault_state"] = "setup_pin"
            await update.message.reply_text(
                with_footer("✅ ᴄᴏʀʀᴇᴄᴛ! ɴᴏᴡ sᴇɴᴅ ʏᴏᴜʀ ɴᴇᴡ ᴘɪɴ:"),
                reply_markup=back_btn("menu:vault"),
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ ᴡʀᴏɴɢ ᴘɪɴ.")


def get_handlers():
    return [
        CommandHandler("vault", cmd_vault),
        CallbackQueryHandler(cbq_vault, pattern=r"^vault:"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vault_input),
    ]
