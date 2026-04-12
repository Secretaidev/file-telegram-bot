"""
vault bot — file operations handler
send, rename, delete, move, copy, favorite, info, share trigger
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from middlewares import auth_middleware, rate_limit_middleware
from services import FileService, UserService, ShareService
from utils import (
    file_actions, file_delete_confirm, share_options, with_footer,
    format_size, category_icon, format_dt, channel_log, back_btn
)
from config import cfg

log = logging.getLogger(__name__)


async def cbq_file_ops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    file_db_id = parts[2] if len(parts) > 2 else ""

    if action == "send":
        await _send_file(q, context, file_db_id)

    elif action == "fav":
        await _toggle_favorite(q, context, file_db_id)

    elif action == "rename":
        await _prompt_rename(q, context, file_db_id)

    elif action == "delete":
        doc = await FileService.get_by_id(file_db_id)
        if not doc:
            await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
            return
        await q.answer()
        await q.edit_message_text(
            with_footer(
                f"🗑  <b>ᴄᴏɴꜰɪʀᴍ ᴅᴇʟᴇᴛᴇ</b>\n\n"
                f"ᴀʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴅᴇʟᴇᴛᴇ:\n"
                f"<b>{doc['file_name']}</b>?"
            ),
            reply_markup=file_delete_confirm(file_db_id),
            parse_mode="HTML",
        )

    elif action == "delete_confirm":
        await _do_delete(q, context, file_db_id)

    elif action == "info":
        await _show_info(q, context, file_db_id)

    elif action == "share":
        await q.answer()
        doc = await FileService.get_by_id(file_db_id)
        if not doc:
            await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
            return
        await q.edit_message_text(
            with_footer(f"🔗  <b>sʜᴀʀᴇ ʟɪɴᴋ</b>\n\nᴄʜᴏᴏsᴇ ʟɪɴᴋ ᴇxᴘɪʀʏ ꜰᴏʀ:\n<b>{doc['file_name']}</b>"),
            reply_markup=share_options(file_db_id),
            parse_mode="HTML",
        )

    elif action == "copy":
        await _copy_file(q, context, file_db_id)

    elif action == "move":
        await _prompt_move(q, context, file_db_id)


async def _send_file(q, context, file_db_id: str) -> None:
    await q.answer("sᴇɴᴅɪɴɢ…")
    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
        return

    icon = category_icon(doc.get("category", "other"))
    caption = with_footer(f"{icon}  <b>{doc['file_name']}</b>\n{format_size(doc.get('file_size',0))}")

    try:
        await context.bot.copy_message(
            chat_id=q.from_user.id,
            from_chat_id=cfg.STORAGE_CHANNEL_ID,
            message_id=doc["message_id"],
            caption=caption,
            parse_mode="HTML",
        )
        await FileService.increment_downloads(file_db_id)
        await channel_log(
            context.bot, "download", q.from_user.id, q.from_user.username,
            details={"file": doc["file_name"]},
        )
    except Exception as e:
        log.error("send_file error: %s", e)
        await q.answer("❌ ꜰᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ꜰɪʟᴇ.", show_alert=True)


async def _toggle_favorite(q, context, file_db_id: str) -> None:
    user_id = q.from_user.id
    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
        return
    is_now_fav = await UserService.toggle_favorite(user_id, file_db_id)
    label = "💛 ᴀᴅᴅᴇᴅ ᴛᴏ ꜰᴀᴠᴏʀɪᴛᴇs" if is_now_fav else "🩶 ʀᴇᴍᴏᴠᴇᴅ ꜰʀᴏᴍ ꜰᴀᴠᴏʀɪᴛᴇs"
    await q.answer(label)
    await q.edit_message_reply_markup(
        reply_markup=file_actions(file_db_id, is_vault=doc.get("is_vault", False), is_favorite=is_now_fav)
    )


async def _prompt_rename(q, context, file_db_id: str) -> None:
    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
        return
    await q.answer()
    context.user_data["renaming_file"] = file_db_id
    await q.edit_message_text(
        with_footer(
            f"✏️  <b>ʀᴇɴᴀᴍᴇ ꜰɪʟᴇ</b>\n\n"
            f"ᴄᴜʀʀᴇɴᴛ ɴᴀᴍᴇ: <code>{doc['file_name']}</code>\n\n"
            "sᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ɴᴀᴍᴇ:"
        ),
        reply_markup=back_btn(f"file:view:{file_db_id}"),
        parse_mode="HTML",
    )


async def handle_rename_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "renaming_file" not in context.user_data:
        return
    file_db_id = context.user_data.pop("renaming_file")
    new_name = update.message.text.strip()
    user_id = update.effective_user.id

    success = await FileService.rename(file_db_id, new_name, user_id)
    if success:
        await update.message.reply_text(
            with_footer(f"✅ ꜰɪʟᴇ ʀᴇɴᴀᴍᴇᴅ ᴛᴏ: <code>{new_name}</code>"),
            reply_markup=file_actions(file_db_id),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text("❌ ʀᴇɴᴀᴍᴇ ꜰᴀɪʟᴇᴅ.")


async def _do_delete(q, context, file_db_id: str) -> None:
    await q.answer()
    user_id = q.from_user.id
    doc = await FileService.soft_delete(file_db_id, user_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ɴᴏ ᴘᴇʀᴍɪssɪᴏɴ.", show_alert=True)
        return

    await q.edit_message_text(
        with_footer(f"🗑  <b>ᴅᴇʟᴇᴛᴇᴅ</b>\n\n<code>{doc['file_name']}</code> ʜᴀs ʙᴇᴇɴ ᴍᴏᴠᴇᴅ ᴛᴏ ᴛʀᴀsʜ."),
        reply_markup=back_btn("menu:files"),
        parse_mode="HTML",
    )
    await channel_log(
        context.bot, "delete", user_id, q.from_user.username,
        details={"file": doc["file_name"]},
    )


async def _show_info(q, context, file_db_id: str) -> None:
    await q.answer()
    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
        return

    icon = category_icon(doc.get("category", "other"))
    text = (
        f"{icon}  <b>ꜰɪʟᴇ ɪɴꜰᴏ</b>\n\n"
        f"ɴᴀᴍᴇ:       <code>{doc['file_name']}</code>\n"
        f"sɪᴢᴇ:       {format_size(doc.get('file_size', 0))}\n"
        f"ᴛʏᴘᴇ:       {doc.get('mime_type', '—')}\n"
        f"ᴄᴀᴛᴇɢᴏʀʏ:  {doc.get('category', '—')}\n"
        f"ᴛᴀɢs:       {', '.join(doc.get('tags', [])) or '—'}\n"
        f"ᴠɪᴇᴡs:      {doc.get('views', 0)}\n"
        f"ᴅᴏᴡɴʟᴏᴀᴅs: {doc.get('downloads', 0)}\n"
        f"ᴠᴀᴜʟᴛ:      {'🔐 ʏᴇs' if doc.get('is_vault') else '❌ ɴᴏ'}\n"
        f"ᴜᴘʟᴏᴀᴅᴇᴅ:  {format_dt(doc['created_at'])}"
    )
    await q.edit_message_text(
        with_footer(text),
        reply_markup=file_actions(file_db_id, is_vault=doc.get("is_vault", False)),
        parse_mode="HTML",
    )


async def _copy_file(q, context, file_db_id: str) -> None:
    await q.answer("📋 ꜰɪʟᴇ ʟɪɴᴋ ᴄᴏᴘɪᴇᴅ ᴛᴏ ʙᴜꜰꜰᴇʀ.", show_alert=True)
    context.user_data["clipboard"] = file_db_id


async def _prompt_move(q, context, file_db_id: str) -> None:
    await q.answer()
    context.user_data["moving_file"] = file_db_id
    await q.edit_message_text(
        with_footer(
            "📁  <b>ᴍᴏᴠᴇ ꜰɪʟᴇ</b>\n\n"
            "sᴇɴᴅ ᴛʜᴇ ᴛᴀʀɢᴇᴛ ꜰᴏʟᴅᴇʀ ɴᴀᴍᴇ ᴏʀ ᴛᴀᴘ ✖️ ᴛᴏ ᴍᴏᴠᴇ ᴛᴏ ʀᴏᴏᴛ:"
        ),
        reply_markup=back_btn(f"file:view:{file_db_id}"),
        parse_mode="HTML",
    )


def get_handlers():
    return [
        CallbackQueryHandler(cbq_file_ops, pattern=r"^file:(send|fav|rename|delete|delete_confirm|info|share|copy|move):"),
    ]
