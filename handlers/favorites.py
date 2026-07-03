"""
vault bot — favorites & recent files handler
view favorited files, recently accessed files
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from middlewares import auth_middleware
from services import UserService, FileService
from utils import (
    with_footer, category_icon, format_size, format_dt,
    file_actions, back_btn, btn, row, build
)
from config import cfg

log = logging.getLogger(__name__)


async def cmd_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    user_id = update.effective_user.id
    await _show_favorites(update, context, user_id, page=0, from_message=True)


async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return
    user_id = update.effective_user.id
    await _show_recent(update, context, user_id, from_message=True)


async def cbq_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    user_id = q.from_user.id

    if action == "list":
        await q.answer()
        page = int(parts[2]) if len(parts) > 2 else 0
        await _show_favorites(update, context, user_id, page)

    elif action == "recent":
        await q.answer()
        await _show_recent(update, context, user_id)


async def _show_favorites(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    page: int = 0,
    from_message: bool = False,
) -> None:
    fav_ids = await UserService.get_favorites(user_id)

    if not fav_ids:
        text = with_footer(
            "⭐  <b>ꜰᴀᴠᴏʀɪᴛᴇs</b>\n\n"
            "ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ꜰᴀᴠᴏʀɪᴛᴇᴅ ᴀɴʏ ꜰɪʟᴇs ʏᴇᴛ.\n\n"
            "ᴛᴀᴘ ⭐ ᴏɴ ᴀɴʏ ꜰɪʟᴇ ᴛᴏ ᴀᴅᴅ ɪᴛ ʜᴇʀᴇ."
        )
        markup = build(
            row(btn("⏱  ʀᴇᴄᴇɴᴛ ꜰɪʟᴇs", "favs:recent"),
                btn("◀️  ʙᴀᴄᴋ", "menu:start")),
        )
        if from_message:
            await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
        return

    page_size = cfg.PAGE_SIZE
    total = len(fav_ids)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    chunk_ids = fav_ids[page * page_size:(page + 1) * page_size]

    # Batch resolve file documents
    docs_map = await FileService.get_by_ids(chunk_ids)

    rows = []
    for fid in chunk_ids:
        doc = docs_map.get(fid)
        if not doc:
            continue
        icon = category_icon(doc.get("category", "other"))
        label = f"{icon}  {doc['file_name'][:35]}"
        rows.append(row(btn(label, f"file:view:{fid}")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"favs:list:{page - 1}"))
    nav.append(btn(f"{page + 1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"favs:list:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append(row(
        btn("⏱  ʀᴇᴄᴇɴᴛ", "favs:recent"),
        btn("◀️  ʙᴀᴄᴋ", "menu:start"),
    ))

    text = with_footer(f"⭐  <b>ꜰᴀᴠᴏʀɪᴛᴇs</b> ({total} ꜰɪʟᴇs)")
    markup = build(*rows)

    if from_message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")


async def _show_recent(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    from_message: bool = False,
) -> None:
    recent_ids = await UserService.get_recent(user_id)

    if not recent_ids:
        text = with_footer(
            "⏱  <b>ʀᴇᴄᴇɴᴛ ꜰɪʟᴇs</b>\n\n"
            "ɴᴏ ʀᴇᴄᴇɴᴛʟʏ ᴀᴄᴄᴇssᴇᴅ ꜰɪʟᴇs ʏᴇᴛ."
        )
        markup = back_btn("menu:start")
        if from_message:
            await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
        return

    # Batch resolve file documents
    docs_map = await FileService.get_by_ids(recent_ids[:10])

    rows = []
    for fid in recent_ids[:10]:
        doc = docs_map.get(fid)
        if not doc:
            continue
        icon = category_icon(doc.get("category", "other"))
        label = f"{icon}  {doc['file_name'][:35]}"
        rows.append(row(btn(label, f"file:view:{fid}")))

    rows.append(row(
        btn("⭐  ꜰᴀᴠᴏʀɪᴛᴇs", "favs:list:0"),
        btn("◀️  ʙᴀᴄᴋ", "menu:start"),
    ))

    text = with_footer(f"⏱  <b>ʀᴇᴄᴇɴᴛ ꜰɪʟᴇs</b> (ʟᴀsᴛ {len(recent_ids[:10])})")
    markup = build(*rows)

    if from_message:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")


def get_handlers():
    return [
        CommandHandler("favorites", cmd_favorites),
        CommandHandler("recent", cmd_recent),
        CallbackQueryHandler(cbq_favorites, pattern=r"^favs:"),
    ]
