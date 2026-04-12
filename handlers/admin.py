"""
vault bot — admin panel handler
full admin control: users, stats, broadcast, payments, logs, maintenance, backup
"""

from __future__ import annotations
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from middlewares import require_admin
from services import UserService, FileService, SubscriptionService, BackupService
from utils import (
    admin_panel, admin_user_actions, pending_payments_list,
    with_footer, format_size, format_dt, channel_log, back_btn,
    btn, row, build
)
from config import cfg

log = logging.getLogger(__name__)

_MAINTENANCE_MODE = False


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not cfg.is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        with_footer("⚙️  <b>ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ</b>\n\nᴡᴇʟᴄᴏᴍᴇ, ᴀᴅᴍɪɴ."),
        reply_markup=admin_panel(),
        parse_mode="HTML",
    )


async def cbq_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _MAINTENANCE_MODE
    q = update.callback_query
    if not cfg.is_admin(q.from_user.id):
        await q.answer("⛔ ᴀᴅᴍɪɴ ᴏɴʟʏ.", show_alert=True)
        return

    parts = q.data.split(":")
    action = parts[1]

    if action == "panel":
        await q.answer()
        await q.edit_message_text(
            with_footer("⚙️  <b>ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ</b>"),
            reply_markup=admin_panel(),
            parse_mode="HTML",
        )

    elif action == "stats":
        await q.answer()
        await _show_stats(q, context)

    elif action == "users":
        await q.answer()
        page = int(parts[2]) if len(parts) > 2 else 0
        await _show_users(q, context, page)

    elif action == "payments":
        await q.answer()
        await _show_pending_payments(q, context)

    elif action == "logs":
        await q.answer()
        await _show_logs(q, context)

    elif action == "broadcast":
        await q.answer()
        context.user_data["admin_state"] = "broadcast"
        await q.edit_message_text(
            with_footer(
                "📢  <b>ʙʀᴏᴀᴅᴄᴀsᴛ</b>\n\n"
                "sᴇɴᴅ ᴀɴʏ ᴍᴇssᴀɢᴇ (ᴛᴇxᴛ/ᴍᴇᴅɪᴀ).\n"
                "ɪᴛ ᴡɪʟʟ ʙᴇ ꜰᴏʀᴡᴀʀᴅᴇᴅ ᴛᴏ ᴀʟʟ ᴜsᴇʀs."
            ),
            reply_markup=back_btn("admin:panel"),
            parse_mode="HTML",
        )

    elif action == "maintenance":
        await q.answer()
        _MAINTENANCE_MODE = not _MAINTENANCE_MODE
        status = "🔴 ᴏɴ" if _MAINTENANCE_MODE else "🟢 ᴏꜰꜰ"
        await q.edit_message_text(
            with_footer(f"🛠  <b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴍᴏᴅᴇ: {status}</b>"),
            reply_markup=admin_panel(),
            parse_mode="HTML",
        )
        from utils.logger import system_log
        await system_log(context.bot, f"maintenance mode toggled: {_MAINTENANCE_MODE}")

    elif action == "backup":
        await q.answer("⏳ ᴄʀᴇᴀᴛɪɴɢ ʙᴀᴄᴋᴜᴘ…")
        try:
            path = await BackupService.create_backup()
            await BackupService.send_to_channels(context.bot, path)
            await BackupService.cleanup_old_backups(keep=5)
            await q.edit_message_text(
                with_footer(f"💾  <b>ʙᴀᴄᴋᴜᴘ ᴄᴏᴍᴘʟᴇᴛᴇ</b>\n\n<code>{path}</code>"),
                reply_markup=back_btn("admin:panel"),
                parse_mode="HTML",
            )
            from utils.logger import system_log
            await system_log(context.bot, f"manual backup created: {path}")
        except Exception as e:
            await q.edit_message_text(f"❌ ʙᴀᴄᴋᴜᴘ ꜰᴀɪʟᴇᴅ: {e}", reply_markup=back_btn("admin:panel"))

    elif action == "toggleban":
        user_id = int(parts[2])
        user_doc = await UserService.get(user_id)
        if not user_doc:
            await q.answer("user not found", show_alert=True)
            return
        is_banned = user_doc.get("is_banned", False)
        if is_banned:
            await UserService.unban(user_id)
            await q.answer("✅ ᴜsᴇʀ ᴜɴʙᴀɴɴᴇᴅ.")
        else:
            await UserService.ban(user_id)
            await q.answer("🚫 ᴜsᴇʀ ʙᴀɴɴᴇᴅ.")
        is_premium = user_doc.get("role") in ("premium", "admin", "owner")
        await q.edit_message_reply_markup(
            reply_markup=admin_user_actions(user_id, not is_banned, is_premium)
        )
        await channel_log(
            context.bot, "ban" if not is_banned else "unban",
            q.from_user.id, q.from_user.username,
            details={"target_user": user_id},
        )

    elif action == "togglepremium":
        user_id = int(parts[2])
        user_doc = await UserService.get(user_id)
        if not user_doc:
            await q.answer("user not found", show_alert=True)
            return
        is_premium = user_doc.get("role") in ("premium",)
        if is_premium:
            await SubscriptionService.revoke(user_id)
            await q.answer("❌ ᴘʀᴇᴍɪᴜᴍ ʀᴇᴠᴏᴋᴇᴅ.")
        else:
            await SubscriptionService.grant(user_id, "monthly", q.from_user.id)
            await q.answer("💎 ᴘʀᴇᴍɪᴜᴍ ɢʀᴀɴᴛᴇᴅ (1 ᴍᴏɴᴛʜ).")
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=with_footer("🎉 ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ɢʀᴀɴᴛᴇᴅ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇss! 💎"),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        await channel_log(
            context.bot, "admin", q.from_user.id, q.from_user.username,
            details={"action": "toggle_premium", "target": user_id},
        )

    elif action == "deletefiles":
        user_id = int(parts[2])
        user_doc = await UserService.get(user_id)
        if not user_doc:
            await q.answer("user not found", show_alert=True)
            return
        from database import files as files_col
        result = await files_col().update_many(
            {"owner_id": user_id},
            {"$set": {"is_deleted": True}},
        )
        await UserService.update(user_id, {"storage_used": 0, "file_count": 0})
        await q.answer(f"🗑 ᴅᴇʟᴇᴛᴇᴅ {result.modified_count} ꜰɪʟᴇs.")
        await channel_log(
            context.bot, "admin", q.from_user.id, q.from_user.username,
            details={"action": "delete_all_files", "target": user_id, "count": result.modified_count},
        )
        await _show_user_stats(q, context, user_id)

    elif action == "userstats":
        user_id = int(parts[2])
        await _show_user_stats(q, context, user_id)

    elif action == "reviewpay":
        payment_id = parts[2]
        payment = await SubscriptionService.get_payment(payment_id)
        if not payment:
            await q.answer("not found", show_alert=True)
            return
        await q.answer()
        text = (
            f"💳  <b>ᴘᴀʏᴍᴇɴᴛ ʀᴇᴠɪᴇᴡ</b>\n\n"
            f"ᴜsᴇʀ:   <code>{payment['user_id']}</code>\n"
            f"ᴘʟᴀɴ:   {payment['plan']}\n"
            f"ᴀᴍᴏᴜɴᴛ: ₹{payment['amount']}\n"
            f"ᴅᴀᴛᴇ:   {format_dt(payment['created_at'])}"
        )
        from utils.keyboards import payment_admin_review
        await q.edit_message_text(
            with_footer(text),
            reply_markup=payment_admin_review(payment_id),
            parse_mode="HTML",
        )


async def _show_stats(q, context) -> None:
    total_users = await UserService.count_all()
    premium_users = await UserService.count_premium()
    banned_users = await UserService.count_banned()
    total_files = await FileService.total_count()
    total_size = await FileService.total_size()
    cat_breakdown = await FileService.category_breakdown()
    pay_stats = await SubscriptionService.count_payments_by_status()

    breakdown_lines = "\n".join(
        f"  {cat}: {count}" for cat, count in cat_breakdown.items()
    )

    text = (
        f"📊  <b>sʏsᴛᴇᴍ sᴛᴀᴛs</b>\n\n"
        f"👥 <b>ᴜsᴇʀs</b>\n"
        f"├ ᴛᴏᴛᴀʟ:    {total_users}\n"
        f"├ ᴘʀᴇᴍɪᴜᴍ: {premium_users}\n"
        f"└ ʙᴀɴɴᴇᴅ:  {banned_users}\n\n"
        f"📁 <b>ꜰɪʟᴇs</b>\n"
        f"├ ᴛᴏᴛᴀʟ: {total_files}\n"
        f"└ sɪᴢᴇ:  {format_size(total_size)}\n\n"
        f"📂 <b>ᴄᴀᴛᴇɢᴏʀɪᴇs</b>\n{breakdown_lines}\n\n"
        f"💳 <b>ᴘᴀʏᴍᴇɴᴛs</b>\n"
        f"├ ᴘᴇɴᴅɪɴɢ:  {pay_stats.get('pending', 0)}\n"
        f"├ ᴀᴘᴘʀᴏᴠᴇᴅ: {pay_stats.get('approved', 0)}\n"
        f"└ ʀᴇᴊᴇᴄᴛᴇᴅ: {pay_stats.get('rejected', 0)}"
    )
    await q.edit_message_text(with_footer(text), reply_markup=back_btn("admin:panel"), parse_mode="HTML")


async def _show_users(q, context, page: int) -> None:
    all_users = await UserService.list_users(skip=page * 8, limit=8)
    if not all_users:
        await q.answer("no users found", show_alert=True)
        return

    rows = []
    for u in all_users:
        badge = {"premium": "💎", "admin": "⚙️", "owner": "👑", "banned": "🚫"}.get(u.get("role"), "👤")
        name = u.get("username") or u.get("full_name", str(u["user_id"]))
        rows.append(row(btn(f"{badge} {name}", f"admin:userstats:{u['user_id']}")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"admin:users:{page-1}"))
    nav.append(btn(f"p{page+1}", "noop"))
    nav.append(btn("▶️", f"admin:users:{page+1}"))
    rows.append(nav)
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "admin:panel")))

    await q.edit_message_text(
        with_footer(f"👥  <b>ᴜsᴇʀs</b> (page {page+1})"),
        reply_markup=build(*rows),
        parse_mode="HTML",
    )


async def _show_pending_payments(q, context) -> None:
    pending = await SubscriptionService.list_pending()
    if not pending:
        await q.edit_message_text(
            with_footer("💳  ɴᴏ ᴘᴇɴᴅɪɴɢ ᴘᴀʏᴍᴇɴᴛs."),
            reply_markup=back_btn("admin:panel"),
            parse_mode="HTML",
        )
        return
    await q.edit_message_text(
        with_footer(f"💳  <b>ᴘᴇɴᴅɪɴɢ ᴘᴀʏᴍᴇɴᴛs</b> ({len(pending)})"),
        reply_markup=pending_payments_list(pending),
        parse_mode="HTML",
    )


async def _show_logs(q, context) -> None:
    from database import logs
    cursor = logs().find({}).sort("created_at", -1).limit(10)
    recent = await cursor.to_list(10)

    if not recent:
        await q.edit_message_text(
            with_footer("📋  ɴᴏ ʟᴏɢs ʏᴇᴛ."),
            reply_markup=back_btn("admin:panel"),
            parse_mode="HTML",
        )
        return

    lines = [f"📋  <b>ʀᴇᴄᴇɴᴛ ʟᴏɢs</b>\n"]
    for entry in recent:
        ts = entry["created_at"].strftime("%H:%M")
        lines.append(f"<code>{ts}</code> {entry['action']} → user {entry['user_id']}")

    await q.edit_message_text(
        with_footer("\n".join(lines)),
        reply_markup=back_btn("admin:panel"),
        parse_mode="HTML",
    )


async def _show_user_stats(q, context, user_id: int) -> None:
    user_doc = await UserService.get(user_id)
    if not user_doc:
        await q.answer("user not found", show_alert=True)
        return

    is_premium = user_doc.get("role") in ("premium", "admin", "owner")
    is_banned = user_doc.get("is_banned", False)

    text = (
        f"👤  <b>ᴜsᴇʀ ᴅᴇᴛᴀɪʟs</b>\n\n"
        f"ɪᴅ:      <code>{user_id}</code>\n"
        f"ɴᴀᴍᴇ:    {user_doc.get('full_name', '—')}\n"
        f"ᴜsᴇʀɴᴀᴍᴇ: @{user_doc.get('username') or '—'}\n"
        f"ʀᴏʟᴇ:    {user_doc.get('role', 'user')}\n"
        f"ʙᴀɴɴᴇᴅ:  {'🚫 ʏᴇs' if is_banned else '✅ ɴᴏ'}\n"
        f"ꜰɪʟᴇs:   {user_doc.get('file_count', 0)}\n"
        f"sᴛᴏʀᴀɢᴇ: {format_size(user_doc.get('storage_used', 0))}\n"
        f"ᴊᴏɪɴᴇᴅ:  {format_dt(user_doc['joined_at'])}"
    )
    await q.edit_message_text(
        with_footer(text),
        reply_markup=admin_user_actions(user_id, is_banned, is_premium),
        parse_mode="HTML",
    )


# ── broadcast ─────────────────────────────────────────────────────────────────

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("admin_state") != "broadcast":
        return
    if not cfg.is_admin(update.effective_user.id):
        return

    context.user_data.pop("admin_state", None)
    message = update.message

    from database import users
    all_users = await users().find({}, {"user_id": 1}).to_list(None)
    success = 0
    failed = 0

    status_msg = await message.reply_text(f"📢 ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴛᴏ {len(all_users)} ᴜsᴇʀs…")

    for user in all_users:
        try:
            await message.copy(chat_id=user["user_id"])
            success += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        with_footer(
            f"📢  <b>ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ</b>\n\n"
            f"✅ sᴇɴᴛ: {success}\n"
            f"❌ ꜰᴀɪʟᴇᴅ: {failed}"
        ),
        parse_mode="HTML",
    )

    await channel_log(
        context.bot, "admin", update.effective_user.id, update.effective_user.username,
        details={"action": "broadcast", "sent": success, "failed": failed},
    )


# ── admin commands ────────────────────────────────────────────────────────────

@require_admin
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ᴜsᴀɢᴇ: /ban <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.")
        return
    await UserService.ban(user_id)
    await update.message.reply_text(f"🚫 ᴜsᴇʀ {user_id} ʙᴀɴɴᴇᴅ.")
    await channel_log(context.bot, "ban", update.effective_user.id, update.effective_user.username, details={"target": user_id})


@require_admin
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("ᴜsᴀɢᴇ: /unban <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.")
        return
    await UserService.unban(user_id)
    await update.message.reply_text(f"✅ ᴜsᴇʀ {user_id} ᴜɴʙᴀɴɴᴇᴅ.")


@require_admin
async def cmd_grant(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("ᴜsᴀɢᴇ: /grant <user_id> <monthly|yearly>")
        return
    try:
        user_id = int(context.args[0])
        plan = context.args[1]
    except ValueError:
        await update.message.reply_text("ɪɴᴠᴀʟɪᴅ ᴀʀɢs.")
        return
    await SubscriptionService.grant(user_id, plan, update.effective_user.id)
    await update.message.reply_text(f"💎 ᴘʀᴇᴍɪᴜᴍ ({plan}) ɢʀᴀɴᴛᴇᴅ ᴛᴏ {user_id}.")
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=with_footer("🎉 ʏᴏᴜ'ᴠᴇ ʙᴇᴇɴ ɢʀᴀɴᴛᴇᴅ ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴄᴇss! 💎"),
            parse_mode="HTML",
        )
    except Exception:
        pass


def get_handlers():
    return [
        CommandHandler("admin", cmd_admin),
        CommandHandler("ban", cmd_ban),
        CommandHandler("unban", cmd_unban),
        CommandHandler("grant", cmd_grant),
        CallbackQueryHandler(cbq_admin, pattern=r"^admin:"),
    ]


def is_maintenance() -> bool:
    return _MAINTENANCE_MODE
