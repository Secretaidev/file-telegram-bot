"""
vault bot — logging system
dual output: console + private telegram log channel
"""

from __future__ import annotations
import logging
import asyncio
from datetime import datetime
from typing import Optional, Any, Dict
from telegram import Bot
from config import cfg

# ── console logger setup ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("vault")

# ── icons for log levels ──────────────────────────────────────────────────────
_ICONS = {
    "upload":   "📤",
    "download": "📥",
    "delete":   "🗑",
    "search":   "🔍",
    "vault":    "🔐",
    "share":    "🔗",
    "payment":  "💳",
    "auth":     "🔑",
    "admin":    "⚙️",
    "error":    "❌",
    "ban":      "🚫",
    "unban":    "✅",
    "join":     "👋",
    "system":   "🤖",
    "backup":   "💾",
}


_main_bot: Bot | None = None

def get_main_bot() -> Bot:
    global _main_bot
    if _main_bot is None:
        _main_bot = Bot(token=cfg.BOT_TOKEN)
    return _main_bot


async def channel_log(
    bot: Bot,
    action: str,
    user_id: int,
    username: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    level: str = "info",
) -> None:
    # ── persist to MongoDB logs collection ────────────────────────────────────
    try:
        from database import logs as logs_col, log_doc as mk_log
        await logs_col().insert_one(mk_log(user_id, action, details or {}))
    except Exception as e:
        log.warning("failed to write log to db: %s", e)

    # ── send to telegram log channel ──────────────────────────────────────────
    if not cfg.LOG_CHANNEL_ID:
        return

    icon = _ICONS.get(action, "📋")
    user_ref = f"@{username}" if username else f"id:{user_id}"
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Detect if bot is clone bot (different token) and format details accordingly
    bot_info = ""
    try:
        if bot.token != cfg.BOT_TOKEN:
            bot_info = f"\n├ ʙᴏᴛ: <i>ᴄʟᴏɴᴇ ʙᴏᴛ</i>"
    except Exception:
        pass

    lines = [
        f"{icon} <b>{action.upper()}</b>",
        f"├ ᴜsᴇʀ: <code>{user_id}</code> ({user_ref}){bot_info}",
        f"├ ᴛɪᴍᴇ: <code>{ts} UTC</code>",
    ]
    import html
    if details:
        for k, v in details.items():
            k_esc = html.escape(str(k))
            v_esc = html.escape(str(v))
            lines.append(f"├ {k_esc}: <code>{v_esc}</code>")

    lines[-1] = lines[-1].replace("├", "└", 1)
    text = "\n".join(lines)

    try:
        main_bot = get_main_bot()
        await main_bot.send_message(
            chat_id=cfg.LOG_CHANNEL_ID,
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        log.warning("failed to send channel log: %s", e)


async def system_log(bot: Bot, message: str) -> None:
    if not cfg.LOG_CHANNEL_ID:
        return
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    text = f"🤖 <b>SYSTEM</b>\n└ {message}\n<code>{ts} UTC</code>"
    try:
        main_bot = get_main_bot()
        await main_bot.send_message(chat_id=cfg.LOG_CHANNEL_ID, text=text, parse_mode="HTML")
    except Exception:
        pass
