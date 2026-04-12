"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — AI assistant handler
Grok-powered human-like assistant for direct messages and group @mentions
"""

from __future__ import annotations
import logging
import asyncio
from typing import Optional
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from config import cfg
from utils import with_footer

log = logging.getLogger(__name__)

_GROK_URL = "https://api.x.ai/v1/chat/completions"

_SYSTEM_PROMPT = (
    "You are a helpful, smart, and friendly assistant inside a Telegram bot called "
    "'Secret File Storage Bot'. You help users with file storage, sharing, premium plans, "
    "and general questions.\n\n"
    "PERSONALITY:\n"
    "- Speak like a real human — warm, concise, and natural.\n"
    "- Keep replies short and crisp. Only say what's necessary.\n"
    "- Use simple, conversational language. Avoid being robotic or overly formal.\n"
    "- If someone says 'hi' or 'hello', greet them warmly and ask how you can help.\n"
    "- Stay on topic — guide users back to the bot's features when relevant.\n\n"
    "EXAMPLES:\n"
    "User: hi  →  Hey! 👋 How can I help you today?\n"
    "User: how do I upload a file?  →  Just send any file directly to this bot — it saves automatically! 📁\n"
    "User: what is premium?  →  Premium gives you unlimited storage + 2GB uploads. Use /premium to upgrade 💎\n\n"
    "Always reply in the same language the user writes in."
)


async def _ask_grok(user_message: str, history: list) -> Optional[str]:
    """Call Grok API and return assistant reply, or None on failure."""
    if not cfg.GROK_API_KEY:
        return None

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    # include last 6 turns of history to keep context manageable
    for turn in history[-6:]:
        messages.append(turn)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": "grok-3-mini",
        "messages": messages,
        "temperature": 0.8,
        "max_tokens": 256,
    }
    headers = {
        "Authorization": f"Bearer {cfg.GROK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(_GROK_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    log.warning("grok api error %d", resp.status)
                    return None
    except Exception as e:
        log.error("grok request failed: %s", e)
        return None


_FALLBACK = (
    "Hey! 👋 I'm here to help with your files.\n"
    "Try /start to see what I can do for you!"
)


async def handle_ai_dm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle direct messages to the bot with AI reply."""
    # only in private chats
    if update.effective_chat.type != "private":
        return

    # don't intercept messages that other handlers are already waiting for
    if context.user_data and (
        context.user_data.get("awaiting_search")
        or context.user_data.get("awaiting_screenshot")
        or context.user_data.get("vault_state")
        or context.user_data.get("awaiting_broadcast")
        or context.user_data.get("awaiting_rename")
        or context.user_data.get("awaiting_folder_name")
        or context.user_data.get("awaiting_admin_search")
        or context.user_data.get("pending_link_token")
    ):
        return

    text = (update.message.text or "").strip()
    if not text or len(text) > 1000:
        return

    # only reply if GROK_API_KEY is configured
    if not cfg.GROK_API_KEY:
        return

    # maintain per-user conversation history in context
    history: list = context.user_data.setdefault("ai_history", [])

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    reply = await _ask_grok(text, history)
    if not reply:
        return

    # store this turn
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    # keep only last 20 turns
    if len(history) > 20:
        history[:] = history[-20:]

    await update.message.reply_text(reply)


async def handle_ai_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle @bot mentions in group chats with AI reply."""
    if update.effective_chat.type == "private":
        return

    message = update.message
    if not message or not message.text:
        return

    bot_username = context.bot.username
    if not bot_username:
        return

    mention = f"@{bot_username}"
    if mention.lower() not in message.text.lower():
        return

    # strip mention from the text
    user_text = message.text.replace(mention, "").strip()
    if not user_text or not cfg.GROK_API_KEY:
        return

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    # groups don't get persistent history — stateless single-turn
    reply = await _ask_grok(user_text, [])
    if reply:
        await message.reply_text(reply)


def get_handlers():
    return [
        # group @mention handler — high priority group (lower number = higher priority)
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            handle_ai_group_mention,
        ),
        # DM handler — catches unhandled text in private chats
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            handle_ai_dm,
        ),
    ]
