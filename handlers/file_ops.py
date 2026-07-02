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

    elif action == "aidesc":
        await _generate_ai_description(q, context, file_db_id)


async def _send_file(q, context, file_db_id: str) -> None:
    await q.answer("sᴇɴᴅɪɴɢ…")
    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
        return

    icon = category_icon(doc.get("category", "other"))
    caption = with_footer(f"{icon}  <b>{doc['file_name']}</b>\n{format_size(doc.get('file_size',0))}")

    try:
        storage_channel = doc.get("storage_channel_id") or cfg.STORAGE_CHANNEL_ID
        await context.bot.copy_message(
            chat_id=q.from_user.id,
            from_chat_id=storage_channel,
            message_id=doc["message_id"],
            caption=caption,
            parse_mode="HTML",
        )
        import asyncio
        asyncio.create_task(FileService.increment_downloads(file_db_id))
        asyncio.create_task(
            channel_log(
                context.bot, "download", q.from_user.id, q.from_user.username,
                details={"file": doc["file_name"]},
            )
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


async def _generate_ai_description(q, context, file_db_id: str) -> None:
    await q.answer("🧠 Analyzing file details...")
    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("File not found.", show_alert=True)
        return

    from config import cfg
    if not cfg.GROK_API_KEY:
        await q.answer("❌ AI Assistant is not configured by owner.", show_alert=True)
        return

    from handlers.ai import _ask_grok
    prompt = (
        f"Provide a short, premium, eye-catching description/summary of this file.\n"
        f"Filename: {doc['file_name']}\n"
        f"Category: {doc.get('category', 'other')}\n"
        f"Size: {format_size(doc.get('file_size', 0))}\n\n"
        f"Provide the response in Hinglish/English. Keep the description under 3 sentences. "
        f"At the end, suggest 3-5 relevant hashtags. "
        f"Use ONLY these HTML tags for formatting: <b>bold</b>, <i>italic</i>, and <code>code</code>. "
        f"Do not use markdown formatting. Format exactly like this:\n\n"
        f"🤖 <b>File Overview:</b>\n"
        f"[Overview description]\n\n"
        f"🏷 <b>Auto Tags:</b>\n"
        f"<code>#tag1</code> <code>#tag2</code> <code>#tag3</code>"
    )

    await q.edit_message_text(
        with_footer(
            f"🤖  <b>ᴀɪ ᴀɴᴀʟʏsɪs ɪɴ ᴘʀᴏɢʀᴇss…</b>\n\n"
            f"Analyzing <code>{doc['file_name']}</code>\n"
            f"Please wait a few seconds."
        ),
        parse_mode="HTML"
    )

    reply = await _ask_grok(prompt, [])
    if not reply:
        await q.edit_message_text(
            with_footer("❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀɪ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ."),
            reply_markup=file_actions(file_db_id, is_vault=doc.get("is_vault", False)),
            parse_mode="HTML"
        )
        return

    # Check favorites status to preserve keyboard actions
    user_id = q.from_user.id
    from handlers.search import _get_user_favs
    is_fav = file_db_id in await _get_user_favs(user_id)

    formatted_text = (
        f"🤖  <b>ᴀɪ ꜰɪʟᴇ ᴅᴇsᴄʀɪᴘᴛɪᴏɴ</b>\n\n"
        f"{reply}\n\n"
        f"📎 ꜰɪʟᴇ: <code>{doc['file_name']}</code>"
    )

    await q.edit_message_text(
        with_footer(formatted_text),
        reply_markup=file_actions(file_db_id, is_vault=doc.get("is_vault", False), is_favorite=is_fav),
        parse_mode="HTML"
    )


def get_handlers():
    return [
        CallbackQueryHandler(cbq_file_ops, pattern=r"^file:(send|fav|rename|delete|delete_confirm|info|share|copy|move|aidesc):"),
    ]
