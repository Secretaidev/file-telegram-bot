"""
vault bot — global error handler & maintenance gate
catches all uncaught exceptions, enforces maintenance mode
"""

from __future__ import annotations
import html
import logging
import traceback
from telegram import Update
from telegram.ext import ContextTypes
from utils.logger import channel_log, system_log
from config import cfg

log = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    log.error("unhandled exception: %s", err, exc_info=context.error)

    if cfg.LOG_CHANNEL_ID:
        safe_tb = html.escape(tb[-1500:])
        msg = (
            f"❌ <b>UNHANDLED ERROR</b>\n\n"
            f"<pre>{safe_tb}</pre>"
        )
        try:
            await context.bot.send_message(
                chat_id=cfg.LOG_CHANNEL_ID,
                text=msg,
                parse_mode="HTML",
            )
        except Exception:
            pass

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ sᴏᴍᴇᴛʜɪɴɢ ᴡᴇɴᴛ ᴡʀᴏɴɢ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.\n"
                "ɪꜰ ᴛʜɪs ᴘᴇʀsɪsᴛs, ᴄᴏɴᴛᴀᴄᴛ @song_assistant"
            )
        except Exception:
            pass


async def maintenance_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.admin import is_maintenance
    if not is_maintenance():
        return

    user = update.effective_user
    if user and cfg.is_admin(user.id):
        return

    if update.message:
        await update.message.reply_text(
            "🛠  <b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ</b>\n\n"
            "ᴛʜᴇ ʙᴏᴛ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀɢᴏɪɴɢ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.\n"
            "ᴘʟᴇᴀsᴇ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ sʜᴏʀᴛʟʏ.",
            parse_mode="HTML",
        )
    elif update.callback_query:
        await update.callback_query.answer(
            "🛠 bot is under maintenance. please try again later.",
            show_alert=True,
        )
