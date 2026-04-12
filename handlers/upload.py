"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — upload handler
handles incoming files, stores to storage channel, saves metadata
"""

from __future__ import annotations
import logging
import random
from telegram import Update, Message
from telegram.ext import ContextTypes, MessageHandler, filters, CommandHandler
from middlewares import auth_middleware, check_membership, rate_limit_middleware
from services import FileService, UserService
from utils import (
    file_actions, with_footer, format_size, category_icon,
    channel_log, get_category
)
from config import cfg

log = logging.getLogger(__name__)

_SUPPORTED = (
    filters.Document.ALL
    | filters.VIDEO
    | filters.AUDIO
    | filters.PHOTO
    | filters.VOICE
    | filters.VIDEO_NOTE
)


async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # let the payment screenshot handler deal with photos when awaiting payment
    if context.user_data.get("awaiting_screenshot"):
        return
    if not await auth_middleware(update, context):
        return
    if not await rate_limit_middleware(update, context):
        return
    if not await check_membership(update, context):
        return

    user = update.effective_user
    message = update.message

    attachment = (
        message.document
        or message.video
        or message.audio
        or (message.photo[-1] if message.photo else None)
        or message.voice
        or message.video_note
    )

    if not attachment:
        return

    is_premium = await UserService.is_premium(user.id)
    upload_limit = cfg.PREMIUM_UPLOAD_LIMIT if is_premium else cfg.FREE_UPLOAD_LIMIT
    storage_limit = cfg.PREMIUM_STORAGE_LIMIT if is_premium else cfg.FREE_STORAGE_LIMIT

    file_size = getattr(attachment, "file_size", 0) or 0

    # 0 = unlimited; only enforce when limit > 0
    if upload_limit > 0 and file_size > upload_limit:
        await message.reply_text(
            f"❌ ꜰɪʟᴇ ᴛᴏᴏ ʟᴀʀɢᴇ.\n\n"
            f"ʏᴏᴜʀ ʟɪᴍɪᴛ: <b>{format_size(upload_limit)}</b>\n"
            f"ꜰɪʟᴇ sɪᴢᴇ: <b>{format_size(file_size)}</b>\n\n"
            + ("ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ ꜰᴏʀ ʜɪɢʜᴇʀ ʟɪᴍɪᴛs — /premium" if not is_premium else ""),
            parse_mode="HTML",
        )
        return

    storage_used = await UserService.get_storage_used(user.id)
    if storage_limit > 0 and storage_used + file_size > storage_limit:
        await message.reply_text(
            f"❌ sᴛᴏʀᴀɢᴇ ꜰᴜʟʟ.\n\n"
            f"ᴜsᴇᴅ: <b>{format_size(storage_used)}</b> / {format_size(storage_limit)}\n"
            + ("💎 /premium ᴛᴏ ᴇxᴘᴀɴᴅ sᴛᴏʀᴀɢᴇ." if not is_premium else ""),
            parse_mode="HTML",
        )
        return

    processing_msg = await message.reply_text("⏳ ᴘʀᴏᴄᴇssɪɴɢ…")

    try:
        folder_id = context.user_data.get("upload_folder_id")
        is_vault = context.user_data.get("upload_to_vault", False)

        # pick a storage channel — distributes files across all configured channels
        channels = cfg.all_storage_channels()
        if not channels:
            await processing_msg.edit_text(
                "❌ ɴᴏ sᴛᴏʀᴀɢᴇ ᴄʜᴀɴɴᴇʟ ᴄᴏɴꜰɪɢᴜʀᴇᴅ. ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ."
            )
            return
        storage_channel = random.choice(channels)

        storage_msg = await context.bot.copy_message(
            chat_id=storage_channel,
            from_chat_id=message.chat_id,
            message_id=message.message_id,
        )

        tags = _extract_tags(message.caption or "")

        doc, is_dup = await FileService.save_file(
            message=message,
            owner_id=user.id,
            folder_id=folder_id,
            is_vault=is_vault,
            tags=tags,
            storage_msg_id=storage_msg.message_id,
            storage_channel_id=storage_channel,
        )

        if not doc:
            await processing_msg.edit_text("❌ ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ. ᴛʀʏ ᴀɢᴀɪɴ.")
            return

        file_db_id = str(doc["_id"])
        icon = category_icon(doc.get("category", "other"))

        if is_dup:
            dup_text = (
                f"⚠️  <b>ᴅᴜᴘʟɪᴄᴀᴛᴇ ᴅᴇᴛᴇᴄᴛᴇᴅ</b>\n\n"
                f"ᴛʜɪs ꜰɪʟᴇ ᴀʟʀᴇᴀᴅʏ ᴇxɪsᴛs ɪɴ ʏᴏᴜʀ sᴛᴏʀᴀɢᴇ.\n"
                f"{icon}  <b>{doc['file_name']}</b>"
            )
            await processing_msg.edit_text(
                with_footer(dup_text),
                reply_markup=file_actions(file_db_id, is_vault=doc.get("is_vault", False)),
                parse_mode="HTML",
            )
            return

        vault_tag = " 🔐 <i>vault</i>" if is_vault else ""
        success_text = (
            f"✅  <b>ᴜᴘʟᴏᴀᴅ sᴜᴄᴄᴇssꜰᴜʟ</b>{vault_tag}\n\n"
            f"{icon}  <b>{doc['file_name']}</b>\n"
            f"├ sɪᴢᴇ:     {format_size(doc.get('file_size', 0))}\n"
            f"├ ᴛʏᴘᴇ:     {doc.get('category', 'other')}\n"
            f"└ ᴛᴀɢs:     {', '.join(tags) if tags else '—'}"
        )
        await processing_msg.edit_text(
            with_footer(success_text),
            reply_markup=file_actions(file_db_id, is_vault=is_vault),
            parse_mode="HTML",
        )

        await UserService.add_to_recent(user.id, file_db_id)

        await channel_log(
            context.bot, "upload", user.id, user.username,
            details={
                "file":   doc["file_name"],
                "size":   format_size(doc.get("file_size", 0)),
                "vault":  str(is_vault),
            },
        )

    except Exception as e:
        log.error("upload error for user %d: %s", user.id, e, exc_info=True)
        await processing_msg.edit_text("❌ ᴜᴘʟᴏᴀᴅ ꜰᴀɪʟᴇᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")

    finally:
        context.user_data.pop("upload_to_vault", None)


def _extract_tags(text: str) -> list:
    return [w[1:].lower() for w in text.split() if w.startswith("#") and len(w) > 1]


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    await update.message.reply_text(
        "📤  <b>sᴇɴᴅ ᴀ ꜰɪʟᴇ</b>\n\n"
        "ᴊᴜsᴛ sᴇɴᴅ ᴀɴʏ ꜰɪʟᴇ, ᴠɪᴅᴇᴏ, ᴀᴜᴅɪᴏ, ᴅᴏᴄ, ᴏʀ ᴘʜᴏᴛᴏ.\n\n"
        "ᴛɪᴘ: ᴀᴅᴅ ʜᴀsʜᴛᴀɢs ɪɴ ᴄᴀᴘᴛɪᴏɴ ᴛᴏ ᴀᴜᴛᴏ-ᴛᴀɢ:\n"
        "<code>#work #project #2024</code>",
        parse_mode="HTML",
    )


def get_handlers():
    return [
        CommandHandler("upload", cmd_upload),
        MessageHandler(_SUPPORTED, handle_upload),
    ]
