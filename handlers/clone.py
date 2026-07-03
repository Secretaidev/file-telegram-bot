"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — bot cloning handler
allows premium users to host and manage their own bot clones
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from middlewares import auth_middleware
from services import BotCloneService, UserService
from utils import with_footer, back_btn, btn, row, build

log = logging.getLogger("vault.clone_handler")


async def cbq_clone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    user_id = q.from_user.id

    # Enforce premium only for cloning bots
    is_premium = await UserService.is_premium(user_id)
    if not is_premium:
        await q.answer("💎 ᴛʜɪs ɪs ᴀ ᴘʀᴇᴍɪᴜᴍ ꜰᴇᴀᴛᴜʀᴇ.", show_alert=True)
        return

    if action == "list":
        await q.answer()
        await _show_clone_list(q, context, user_id)

    elif action == "add":
        await q.answer()
        context.user_data["awaiting_bot_token"] = True
        await q.edit_message_text(
            with_footer(
                "🤖  <b>ᴀᴅᴅ ᴄʟᴏɴᴇ ʙᴏᴛ</b>\n\n"
                "ᴘʟᴇᴀsᴇ sᴇɴᴅ ʏᴏᴜʀ <b>ʙᴏᴛ ᴛᴏᴋᴇɴ</b> now.\n\n"
                "<i>You can get a bot token by creating a new bot with @BotFather on Telegram.</i>"
            ),
            reply_markup=back_btn("clone:list:0"),
            parse_mode="HTML",
        )

    elif action == "delete":
        bot_id = int(parts[2])
        await q.answer()
        try:
            success = await BotCloneService.remove_clone(bot_id)
            if success:
                text = "✅ <b>ᴄʟᴏɴᴇ ʙᴏᴛ sᴛᴏᴘᴘᴇᴅ & ʀᴇᴍᴏᴠᴇᴅ</b>"
            else:
                text = "❌ <b>ᴄʟᴏɴᴇ ʙᴏᴛ ɴᴏᴛ ꜰᴏᴜɴᴅ</b>"
        except Exception as e:
            log.error("failed to delete clone: %s", e)
            text = "❌ <b>ᴇʀʀᴏʀ sᴛᴏᴘᴘɪɴɢ ʙᴏᴛ</b>"

        await q.edit_message_text(
            with_footer(text),
            reply_markup=back_btn("clone:list:0"),
            parse_mode="HTML",
        )


async def _show_clone_list(q, context, user_id: int) -> None:
    clones_list = await BotCloneService.list_user_clones(user_id)

    rows = []
    for bot in clones_list:
        label = f"🤖 @{bot['username']}"
        rows.append(row(
            btn(label, "noop", "primary"),
            btn("❌", f"clone:delete:{bot['bot_id']}", "danger")
        ))

    rows.append(row(btn("➕  ᴀᴅᴅ ɴᴇᴡ ʙᴏᴛ", "clone:add", "success")))
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "menu:premium", "primary")))

    text = (
        "🤖  <b>ᴍʏ ᴄʟᴏɴᴇ ʙᴏᴛs</b>\n\n"
        "Here is the list of your hosted clone bots:\n\n"
        "<i>All clones share the same main storage/database but you are the administrator of your clone.</i>"
    )
    await q.edit_message_text(with_footer(text), reply_markup=build(*rows), parse_mode="HTML")


async def handle_bot_token_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("awaiting_bot_token"):
        return False

    user = update.effective_user
    token = update.message.text.strip()

    # Simple regex check or length validation
    if ":" not in token or len(token) < 20:
        await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ʙᴏᴛ ᴛᴏᴋᴇɴ ꜰᴏʀᴍᴀᴛ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.")
        return True

    # Validate bot token & fetch info temporarily
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
            if resp.status_code != 200:
                raise ValueError()
            data = resp.json()
            if not data.get("ok"):
                raise ValueError()
            bot_username = data["result"]["username"]
    except Exception:
        await update.message.reply_text("❌ ᴜɴᴀʙʟᴇ ᴛᴏ ᴄᴏɴɴᴇᴄᴛ ᴛᴏ ᴛʜɪs ʙᴏᴛ ᴛᴏᴋᴇɴ. ᴠᴇʀɪꜰʏ ɪᴛ with @BotFather.")
        return True

    context.user_data.pop("awaiting_bot_token", None)
    context.user_data["pending_token"] = token
    context.user_data["pending_username"] = bot_username
    context.user_data["awaiting_clone_owner"] = True

    await update.message.reply_text(
        f"🤖 Bot @{bot_username} verified successfully!\n\n"
        f"Now, please send the <b>Telegram Owner ID</b> (numbers only) that will control this bot.\n\n"
        f"<i>Tip: You can send your own user ID: <code>{user.id}</code></i>",
        parse_mode="HTML"
    )
    return True


async def handle_clone_owner_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not context.user_data.get("awaiting_clone_owner"):
        return False

    user = update.effective_user
    owner_id_text = update.message.text.strip()

    if not owner_id_text.isdigit():
        await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ᴏᴡɴᴇʀ ɪᴅ. Please send numbers only.")
        return True

    owner_id = int(owner_id_text)
    token = context.user_data.pop("pending_token")
    bot_username = context.user_data.pop("pending_username")
    context.user_data.pop("awaiting_clone_owner", None)

    try:
        await BotCloneService.add_clone(token, owner_id, user.id)
        await update.message.reply_text(
            f"🎉 <b>ʙᴏᴛ ᴄʟᴏɴᴇ ʟɪᴠᴇ</b> 🎉\n\n"
            f"🤖 Bot: @{bot_username}\n"
            f"👤 Owner: <code>{owner_id}</code>\n\n"
            f"Your bot has been successfully started and is now online! You are the owner of @{bot_username}.",
            parse_mode="HTML"
        )
    except Exception as e:
        log.error("failed to register clone: %s", e)
        await update.message.reply_text(f"❌ ꜰᴀɪʟᴇᴅ ᴛᴏ sᴛᴀʀᴛ ʙᴏᴛ: {str(e)}")

    return True


def get_handlers():
    return [
        CallbackQueryHandler(cbq_clone, pattern=r"^clone:"),
    ]
