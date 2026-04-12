"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — premium & payment handler
plan selection, upi payment instructions, screenshot submission, admin approval
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from middlewares import auth_middleware, check_membership
from services import SubscriptionService, UserService
from utils import (
    premium_menu, payment_plan_select, payment_admin_review,
    with_footer, format_dt, time_left, channel_log, back_btn,
    btn, row, build, url_btn, upi_display_id
)
from config import cfg

log = logging.getLogger(__name__)


async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    if not await check_membership(update, context):
        return
    user_id = update.effective_user.id
    is_premium = await UserService.is_premium(user_id)
    await update.message.reply_text(
        with_footer(_build_premium_text(is_premium)),
        reply_markup=premium_menu(has_premium=is_premium),
        parse_mode="HTML",
    )


async def cbq_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    user_id = q.from_user.id

    if action == "buy":
        plan = parts[2]
        await q.answer()
        await _show_payment_instructions(q, context, plan)

    elif action == "payment":
        await q.answer()
        await q.edit_message_text(
            with_footer(
                "💳  <b>sᴇʟᴇᴄᴛ ᴀ ᴘʟᴀɴ</b>\n\n"
                "👑 ʏᴇᴀʀʟʏ: <b>₹99 / ʏᴇᴀʀ</b>  —  ᴜɴʟɪᴍɪᴛᴇᴅ\n\n"
                "ᴄʜᴏᴏsᴇ ᴀ ᴘʟᴀɴ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ:"
            ),
            reply_markup=payment_plan_select(),
            parse_mode="HTML",
        )

    elif action == "status":
        await q.answer()
        sub = await SubscriptionService.get_active(user_id)
        if sub:
            text = (
                "💎  <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴇ</b>\n\n"
                f"├ ᴘʟᴀɴ:    {sub['plan']}\n"
                f"├ ᴇxᴘɪʀᴇs: {format_dt(sub['expires_at'])}\n"
                f"└ ᴛɪᴍᴇ ʟᴇꜰᴛ: {time_left(sub['expires_at'])}"
            )
        else:
            text = "❌ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴ."
        await q.edit_message_text(
            with_footer(text),
            reply_markup=back_btn("menu:premium"),
            parse_mode="HTML",
        )

    elif action == "compare":
        await q.answer()
        await q.edit_message_text(
            with_footer(_compare_text()),
            reply_markup=back_btn("menu:premium"),
            parse_mode="HTML",
        )

    elif action == "paid":
        await q.answer()
        context.user_data["awaiting_screenshot"] = True
        await q.edit_message_text(
            with_footer(
                "📸  <b>sᴇɴᴅ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ</b>\n\n"
                "ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴛʜᴇ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ɴᴏᴡ.\n"
                "ᴡᴇ ᴡɪʟʟ ᴠᴇʀɪꜰʏ ᴀɴᴅ ᴀᴄᴛɪᴠᴀᴛᴇ ʏᴏᴜʀ ᴘʟᴀɴ\n"
                "ᴡɪᴛʜɪɴ 24 ʜᴏᴜʀs."
            ),
            reply_markup=back_btn("menu:premium"),
            parse_mode="HTML",
        )


async def _show_payment_instructions(q, context, plan: str) -> None:
    from services.subscription_service import PLANS
    plan_data = PLANS.get(plan, PLANS["yearly"])
    amount = plan_data["amount"]

    context.user_data["payment_plan"] = plan
    context.user_data["payment_amount"] = amount
    context.user_data["awaiting_screenshot"] = True

    markup = build(
        row(btn("📸  ɪ'ᴠᴇ ᴘᴀɪᴅ — sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ", "premium:paid")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:premium")),
    )

    text = (
        f"💳  <b>ᴘᴀʏᴍᴇɴᴛ ɪɴsᴛʀᴜᴄᴛɪᴏɴs</b>\n\n"
        f"ᴘʟᴀɴ:   <b>{plan_data['label']}</b>\n"
        f"ᴀᴍᴏᴜɴᴛ: <b>₹{amount}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>1️⃣  ᴏᴘᴇɴ ᴀɴʏ ᴜᴘɪ ᴀᴘᴘ</b>\n"
        f"<i>GPay · PhonePe · Paytm · BHIM</i>\n\n"
        f"<b>2️⃣  ᴘᴀʏ ᴛᴏ ᴜᴘɪ ɪᴅ:</b>\n"
        f"<code>{cfg.UPI_ID}</code>\n\n"
        f"ᴀᴍᴏᴜɴᴛ: <b>₹{amount}</b>\n"
        f"ɴᴏᴛᴇ: <i>{plan_data['label']} premium</i>\n\n"
        f"<b>3️⃣  ᴛᴀᴘ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ & sᴇɴᴅ sᴄʀᴇᴇɴsʜᴏᴛ</b>\n\n"
        f"⏳ <i>ᴀᴄᴛɪᴠᴀᴛɪᴏɴ ᴡɪᴛʜɪɴ 24 ʜᴏᴜʀs.</i>"
    )
    await q.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")



async def handle_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_screenshot"):
        return
    if not (update.message.photo or update.message.document):
        return

    user = update.effective_user
    plan = context.user_data.pop("payment_plan", "yearly")
    context.user_data.pop("awaiting_screenshot", None)

    photo = update.message.photo
    doc = update.message.document
    file_id = photo[-1].file_id if photo else doc.file_id
    msg_id = update.message.message_id

    payment = await SubscriptionService.create_payment(
        user_id=user.id,
        plan=plan,
        screenshot_file_id=file_id,
        screenshot_message_id=msg_id,
    )
    payment_id = str(payment["_id"])

    await update.message.reply_text(
        with_footer(
            "✅  <b>sᴄʀᴇᴇɴsʜᴏᴛ ʀᴇᴄᴇɪᴠᴇᴅ</b>\n\n"
            "ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ɪs ᴜɴᴅᴇʀ ʀᴇᴠɪᴇᴡ.\n"
            "ʏᴏᴜ ᴡɪʟʟ ʙᴇ ɴᴏᴛɪꜰɪᴇᴅ ᴏɴᴄᴇ ᴀᴘᴘʀᴏᴠᴇᴅ."
        ),
        reply_markup=back_btn("menu:start"),
        parse_mode="HTML",
    )

    admin_caption = (
        f"💳  <b>ɴᴇᴡ ᴘᴀʏᴍᴇɴᴛ ʀᴇǫᴜᴇsᴛ</b>\n\n"
        f"ᴜsᴇʀ:   <code>{user.id}</code> (@{user.username or '—'})\n"
        f"ᴘʟᴀɴ:   <b>{plan}</b>\n"
        f"ᴀᴍᴏᴜɴᴛ: ₹{context.user_data.get('payment_amount', '?')}\n"
        f"ɪᴅ:     <code>{payment_id}</code>"
    )

    for admin_id in cfg.ADMIN_IDS + [cfg.OWNER_ID]:
        try:
            if photo:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=admin_caption,
                    reply_markup=payment_admin_review(payment_id),
                    parse_mode="HTML",
                )
            else:
                await context.bot.send_document(
                    chat_id=admin_id,
                    document=file_id,
                    caption=admin_caption,
                    reply_markup=payment_admin_review(payment_id),
                    parse_mode="HTML",
                )
        except Exception as e:
            log.error("failed to notify admin %d: %s", admin_id, e)

    await channel_log(
        context.bot, "payment", user.id, user.username,
        details={"plan": plan, "status": "pending", "payment_id": payment_id},
    )


async def cbq_pay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]

    if action == "plan":
        plan = parts[2]
        context.user_data["payment_plan"] = plan
        context.user_data["payment_amount"] = parts[3]
        context.user_data["awaiting_screenshot"] = True
        await q.answer()
        await _show_payment_instructions(q, context, plan)

    elif action == "approve":
        if not cfg.is_admin(q.from_user.id):
            await q.answer("⛔ ᴀᴅᴍɪɴ ᴏɴʟʏ.", show_alert=True)
            return
        payment_id = parts[2]
        payment = await SubscriptionService.approve_payment(payment_id, q.from_user.id)
        if not payment:
            await q.answer("❌ ɴᴏᴛ ꜰᴏᴜɴᴅ ᴏʀ ᴀʟʀᴇᴀᴅʏ ʀᴇᴠɪᴇᴡᴇᴅ.", show_alert=True)
            return
        await q.answer("✅ ᴘᴀʏᴍᴇɴᴛ ᴀᴘᴘʀᴏᴠᴇᴅ.")
        await q.edit_message_caption(
            caption=(q.message.caption or "") + "\n\n✅ <b>APPROVED</b>",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                chat_id=payment["user_id"],
                text=with_footer(
                    "🎉  <b>ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴀᴛᴇᴅ!</b>\n\n"
                    f"ʏᴏᴜʀ <b>{payment['plan']}</b> ᴘʟᴀɴ ɪs ɴᴏᴡ ᴀᴄᴛɪᴠᴇ.\n"
                    "ᴇɴᴊᴏʏ ᴀʟʟ ᴘʀᴇᴍɪᴜᴍ ꜰᴇᴀᴛᴜʀᴇs! 💎"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass
        await channel_log(
            context.bot, "payment", payment["user_id"], None,
            details={"plan": payment["plan"], "status": "approved", "admin": q.from_user.id},
        )

    elif action == "reject":
        if not cfg.is_admin(q.from_user.id):
            await q.answer("⛔ ᴀᴅᴍɪɴ ᴏɴʟʏ.", show_alert=True)
            return
        payment_id = parts[2]
        payment = await SubscriptionService.reject_payment(payment_id, q.from_user.id)
        if not payment:
            await q.answer("❌ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
            return
        await q.answer("❌ ᴘᴀʏᴍᴇɴᴛ ʀᴇᴊᴇᴄᴛᴇᴅ.")
        await q.edit_message_caption(
            caption=(q.message.caption or "") + "\n\n❌ <b>REJECTED</b>",
            parse_mode="HTML",
        )
        try:
            await context.bot.send_message(
                chat_id=payment["user_id"],
                text=with_footer(
                    "❌  <b>ᴘᴀʏᴍᴇɴᴛ ʀᴇᴊᴇᴄᴛᴇᴅ</b>\n\n"
                    "ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴡᴀs ɴᴏᴛ ᴠᴇʀɪꜰɪᴇᴅ.\n"
                    "ᴄᴏɴᴛᴀᴄᴛ @song_assistant ꜰᴏʀ ʜᴇʟᴘ."
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


def _build_premium_text(is_premium: bool) -> str:
    if is_premium:
        return (
            "💎  <b>ʏᴏᴜ ᴀʀᴇ ᴀ ᴘʀᴇᴍɪᴜᴍ ᴍᴇᴍʙᴇʀ</b> 🎉\n\n"
            "✅ ᴜɴʟɪᴍɪᴛᴇᴅ sᴛᴏʀᴀɢᴇ ᴜɴʟᴏᴄᴋᴇᴅ!\n"
            "✅ ᴜɴʟɪᴍɪᴛᴇᴅ sʜᴀʀᴇ ʟɪɴᴋs\n"
            "✅ ᴜɴʟɪᴍɪᴛᴇᴅ ᴠᴀᴜʟᴛ ꜰɪʟᴇs\n"
            "✅ 2 ɢʙ ꜰɪʟᴇ ᴜᴘʟᴏᴀᴅ"
        )
    return (
        "💎  <b>ᴜᴘɢʀᴀᴅᴇ ᴛᴏ ᴘʀᴇᴍɪᴜᴍ</b>\n\n"
        "ᴜɴʟᴏᴄᴋ ᴛʜᴇ ꜰᴜʟʟ ᴘᴏᴡᴇʀ ᴏꜰ\n"
        "🔒 sᴇᴄʀᴇᴛ ꜰɪʟᴇ sᴛᴏʀᴀɢᴇ ʙᴏᴛ.\n\n"
        "👑 <b>ʏᴇᴀʀʟʏ: ₹99 / ʏᴇᴀʀ</b>  —  ᴜɴʟɪᴍɪᴛᴇᴅ\n\n"
        "💳 <b>ᴘᴀʏ ᴠɪᴀ ɢᴘᴀʏ / ᴘʜᴏɴᴇᴘᴇ / ᴀɴʏ ᴜᴘɪ</b>"
    )


def _compare_text() -> str:
    return (
        "📋  <b>ᴘʟᴀɴ ᴄᴏᴍᴘᴀʀɪsᴏɴ</b>\n\n"
        "<code>"
        "ꜰᴇᴀᴛᴜʀᴇ          ꜰʀᴇᴇ      ᴘʀᴇᴍɪᴜᴍ\n"
        "─────────────────────────────────\n"
        "sᴛᴏʀᴀɢᴇ          500 ᴍʙ    ∞ ᴜɴʟɪᴍɪᴛᴇᴅ\n"
        "ᴜᴘʟᴏᴀᴅ ʟɪᴍɪᴛ     500 ᴍʙ    2 ɢʙ\n"
        "ᴠᴀᴜʟᴛ ꜰɪʟᴇs       ∞         ∞\n"
        "sʜᴀʀᴇ ʟɪɴᴋs       10        ∞\n"
        "ᴀᴅᴠ. ꜰɪʟᴛᴇʀs       ✗        ✓\n"
        "ʙᴜʟᴋ ᴏᴘs           ✗        ✓\n"
        "ᴘʀɪᴏʀɪᴛʏ sᴜᴘᴘᴏʀᴛ  ✗        ✓\n"
        "ᴀɪ ᴀssɪsᴛᴀɴᴄᴇ     ✗        ✓\n"
        "</code>\n\n"
        "👑 <b>ʏᴇᴀʀʟʏ: ₹99 / ʏᴇᴀʀ</b>  —  ᴜɴʟɪᴍɪᴛᴇᴅ"
    )


def get_handlers():
    return [
        CommandHandler("premium", cmd_premium),
        CallbackQueryHandler(cbq_premium, pattern=r"^premium:"),
        CallbackQueryHandler(cbq_pay, pattern=r"^pay:"),
    ]
