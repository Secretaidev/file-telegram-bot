"""
vault bot — global error handler & maintenance gate
catches all uncaught exceptions, enforces maintenance mode
"""

from __future__ import annotations
import html
import logging
import time
import traceback
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from utils.logger import channel_log, system_log
from config import cfg

log = logging.getLogger(__name__)

# Deduplicate identical errors: track (error_message) -> last_sent_timestamp
_error_last_sent: dict = {}
_ERROR_COOLDOWN = 60  # seconds — same error won't be forwarded more than once per minute

# Error messages that are expected/harmless and should never be logged to the channel
_IGNORED_ERROR_FRAGMENTS = (
    "message is not modified",
    "query is too old",
    "message to edit not found",
)


def _is_ignorable(err: Exception) -> bool:
    if isinstance(err, BadRequest):
        msg = str(err).lower()
        return any(frag in msg for frag in _IGNORED_ERROR_FRAGMENTS)
    return False


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error

    # Silently drop harmless / expected Telegram errors
    if _is_ignorable(err):
        log.debug("ignored expected error: %s", err)
        return

    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    log.error("unhandled exception: %s", err, exc_info=context.error)

    # Deduplicate: only forward if we haven't sent this exact error recently
    err_key = str(err)[:200]
    now = time.monotonic()
    if now - _error_last_sent.get(err_key, 0) < _ERROR_COOLDOWN:
        # already reported recently — skip channel log to avoid spam
        pass
    else:
        _error_last_sent[err_key] = now
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
        # Don't reply in channel posts (no real user to reply to)
        if update.effective_chat and update.effective_chat.type == "channel":
            return
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
            "╔══════════════════════════════════╗\n"
            "║  ⚙️  sʏsᴛᴇᴍ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ  ║\n"
            "╚══════════════════════════════════╝\n\n"
            "🛠  <b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ</b>\n\n"
            "ᴛʜᴇ ʙᴏᴛ ɪs ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀɢᴏɪɴɢ sᴄʜᴇᴅᴜʟᴇᴅ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ.\n"
            "ᴀʟʟ ꜰᴇᴀᴛᴜʀᴇs ᴀʀᴇ ᴛᴇᴍᴘᴏʀᴀʀɪʟʏ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ.\n\n"
            "⏳ ᴡᴇ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ sᴏᴏɴ — ᴄʜᴇᴄᴋ @song_assistant ꜰᴏʀ ᴜᴘᴅᴀᴛᴇs.",
            parse_mode="HTML",
        )
    elif update.callback_query:
        await update.callback_query.answer(
            "🛠 Bot is under maintenance. Please check back soon.",
            show_alert=True,
        )
