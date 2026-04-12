"""
vault bot — share link handler
create, view, revoke tokenised share links
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from middlewares import auth_middleware
from services import ShareService, FileService
from utils import (
    share_link_view, with_footer, format_dt, time_left,
    channel_log, back_btn, start_link, btn, row, build, safe_edit
)
from config import cfg

log = logging.getLogger(__name__)

_EXPIRY_MAP = {
    "1h":   1,
    "24h":  24,
    "168h": 168,
    "0h":   0,
}


async def cbq_share(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]

    if action == "create":
        file_db_id = parts[2]
        expiry_key = parts[3] if len(parts) > 3 else "24h"
        hours = _EXPIRY_MAP.get(expiry_key, 24)
        link_doc = await ShareService.create_link(file_db_id, q.from_user.id, expiry_hours=hours)
        await _show_link(q, context, link_doc, file_db_id)

    elif action == "onetime":
        file_db_id = parts[2]
        link_doc = await ShareService.create_link(file_db_id, q.from_user.id, one_time=True)
        await _show_link(q, context, link_doc, file_db_id)

    elif action == "revoke":
        link_db_id = parts[2]
        ok = await ShareService.revoke(link_db_id, q.from_user.id)
        await q.answer("✅ ʟɪɴᴋ ʀᴇᴠᴏᴋᴇᴅ." if ok else "❌ ꜰᴀɪʟᴇᴅ.", show_alert=True)
        if ok:
            await safe_edit(
                q,
                with_footer("🔗  ʟɪɴᴋ ʜᴀs ʙᴇᴇɴ ʀᴇᴠᴏᴋᴇᴅ sᴜᴄᴄᴇssꜰᴜʟʟʏ."),
                reply_markup=back_btn("menu:links"),
                parse_mode="HTML",
            )

    elif action == "detail":
        link_db_id = parts[2]
        from database import links
        from bson import ObjectId
        try:
            link_doc = await links().find_one({"_id": ObjectId(link_db_id)})
        except Exception:
            link_doc = None
        if not link_doc:
            await q.answer("ʟɪɴᴋ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
            return
        await q.answer()
        token = link_doc["token"]
        link_id = str(link_doc["_id"])
        expires = "ɴᴇᴠᴇʀ ᴇxᴘɪʀᴇs" if not link_doc.get("expires_at") else time_left(link_doc["expires_at"])
        one_time_tag = "\n• ᴏɴᴇ-ᴛɪᴍᴇ ʟɪɴᴋ" if link_doc.get("one_time") else ""
        deep_link = start_link(f"dl_{token}")
        text = (
            f"🔗  <b>sʜᴀʀᴇ ʟɪɴᴋ ᴅᴇᴛᴀɪʟ</b>\n\n"
            f"<code>{deep_link}</code>\n\n"
            f"• ᴇxᴘɪʀᴇs: {expires}{one_time_tag}\n"
            f"• ᴅᴏᴡɴʟᴏᴀᴅs: {link_doc.get('downloads', 0)}\n"
            f"• ᴀᴄᴛɪᴠᴇ: {'✅' if link_doc.get('is_active') else '❌'}"
        )
        await safe_edit(
            q,
            with_footer(text),
            reply_markup=share_link_view(token, link_id),
            parse_mode="HTML",
        )

    elif action == "list":
        await q.answer()
        page = int(parts[2]) if len(parts) > 2 else 0
        await _show_links_list(q, context, page)


async def _show_link(q, context, link_doc: dict, file_db_id: str) -> None:
    await q.answer()
    token = link_doc["token"]
    deep_link = start_link(f"dl_{token}")
    link_id = str(link_doc["_id"])

    expires = "ɴᴇᴠᴇʀ ᴇxᴘɪʀᴇs" if not link_doc.get("expires_at") else time_left(link_doc["expires_at"])
    one_time_tag = "\n• ᴏɴᴇ-ᴛɪᴍᴇ ʟɪɴᴋ (sɪɴɢʟᴇ ᴜsᴇ)" if link_doc.get("one_time") else ""

    text = (
        f"🔗  <b>sʜᴀʀᴇ ʟɪɴᴋ ᴄʀᴇᴀᴛᴇᴅ</b>\n\n"
        f"<code>{deep_link}</code>\n\n"
        f"• ᴇxᴘɪʀᴇs: {expires}{one_time_tag}"
    )
    await safe_edit(
        q,
        with_footer(text),
        reply_markup=share_link_view(token, link_id),
        parse_mode="HTML",
    )

    await channel_log(
        context.bot, "share", q.from_user.id, q.from_user.username,
        details={"token": token, "file_id": file_db_id, "expires": expires},
    )


async def _show_links_list(q, context, page: int) -> None:
    user_id = q.from_user.id
    link_list, total = await ShareService.list_user_links(user_id, page)
    total_pages = max(1, (total + 4) // 5)

    if not link_list:
        await safe_edit(
            q,
            with_footer("🔗  <b>ɴᴏ ᴀᴄᴛɪᴠᴇ ʟɪɴᴋs</b>\n\nᴄʀᴇᴀᴛᴇ ᴏɴᴇ ᴠɪᴀ ꜰɪʟᴇ → sʜᴀʀᴇ ʟɪɴᴋ."),
            reply_markup=back_btn("menu:start"),
            parse_mode="HTML",
        )
        return

    rows = []
    for lnk in link_list:
        exp = time_left(lnk["expires_at"]) if lnk.get("expires_at") else "♾"
        rows.append(row(btn(
            f"🔗 {lnk['token'][:8]}… ⏱{exp} 📥{lnk['downloads']}",
            f"share:detail:{lnk['_id']}"
        )))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"share:list:{page-1}"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"share:list:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "menu:start")))

    await safe_edit(
        q,
        with_footer(f"🔗  <b>ᴀᴄᴛɪᴠᴇ ʟɪɴᴋs</b> ({total})"),
        reply_markup=build(*rows),
        parse_mode="HTML",
    )


def get_handlers():
    return [
        CallbackQueryHandler(cbq_share, pattern=r"^share:"),
    ]
