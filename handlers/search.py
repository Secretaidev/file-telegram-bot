"""
vault bot — search handler
full-text search with filters, pagination, sorting, tag suggestions
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from middlewares import auth_middleware, check_membership, rate_limit_middleware
from services import SearchService, FileService, UserService
from utils import (
    search_results, search_filters, file_actions, with_footer,
    format_size, category_icon, back_btn, channel_log
)
from config import cfg

log = logging.getLogger(__name__)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await auth_middleware(update, context):
        return

    query = " ".join(context.args) if context.args else ""
    if query:
        await _do_search(update, context, query, page=0)
        return

    context.user_data["awaiting_search"] = True
    user_id = update.effective_user.id
    pop_tags = await SearchService.get_popular_tags(user_id, limit=6)
    await update.message.reply_text(
        "🔍  <b>sᴇᴀʀᴄʜ ʏᴏᴜʀ ꜰɪʟᴇs</b>\n\n"
        "ᴛʏᴘᴇ ᴀ ꜰɪʟᴇ ɴᴀᴍᴇ, ᴛᴀɢ, ᴏʀ ᴋᴇʏᴡᴏʀᴅ:",
        reply_markup=search_filters(pop_tags),
        parse_mode="HTML",
    )


async def handle_search_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_search"):
        return
    if not await auth_middleware(update, context):
        return
    if not await rate_limit_middleware(update, context):
        return

    context.user_data.pop("awaiting_search", None)
    query = update.message.text.strip()
    await _do_search(update, context, query, page=0)


async def _do_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: str,
    page: int,
    category: str | None = None,
    sort_by: str = "latest",
) -> None:
    user_id = update.effective_user.id
    results, total = await SearchService.search(
        query=query,
        owner_id=user_id,
        category=category or context.user_data.get("search_filter"),
        sort_by=sort_by,
        page=page,
    )

    total_pages = max(1, (total + cfg.SEARCH_PAGE_SIZE - 1) // cfg.SEARCH_PAGE_SIZE)

    if not results:
        text = (
            f"🔍  <b>ɴᴏ ʀᴇsᴜʟᴛs</b>\n\n"
            f"ɴᴏᴛʜɪɴɢ ꜰᴏᴜɴᴅ ꜰᴏʀ: <i>{query}</i>"
        )
        msg_fn = update.message.reply_text if update.message else update.callback_query.edit_message_text
        await msg_fn(with_footer(text), reply_markup=back_btn("menu:search"), parse_mode="HTML")
        return

    text = (
        f"🔍  <b>sᴇᴀʀᴄʜ ʀᴇsᴜʟᴛs</b>\n\n"
        f"ǫᴜᴇʀʏ: <i>{query}</i>\n"
        f"ꜰᴏᴜɴᴅ: <b>{total}</b> ꜰɪʟᴇ{'s' if total != 1 else ''}"
    )
    markup = search_results(results, query, page, total_pages, sort_by)

    if update.message:
        await update.message.reply_text(with_footer(text), reply_markup=markup, parse_mode="HTML")
    else:
        await update.callback_query.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")

    context.user_data["last_search"] = {"query": query, "sort": sort_by, "category": category}

    await channel_log(
        context.bot, "search", user_id, update.effective_user.username,
        details={"query": query, "results": total},
    )


async def cbq_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split(":")
    action = parts[1]

    if action == "page":
        page = int(parts[2])
        q = ":".join(parts[3:])
        last = context.user_data.get("last_search", {})
        await _do_search(update, context, q or last.get("query", ""), page=page)

    elif action == "sort":
        sort_by = parts[2]
        q = ":".join(parts[3:])
        last = context.user_data.get("last_search", {})
        await _do_search(update, context, q or last.get("query", ""), page=0, sort_by=sort_by)

    elif action == "tag":
        tag_name = parts[2]
        await _do_search_by_tag(update, context, tag_name)


async def cbq_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    category = q.data.split(":")[1]
    context.user_data["search_filter"] = None if category == "all" else category
    context.user_data["awaiting_search"] = True

    filter_label = category if category != "all" else "all types"
    await q.edit_message_text(
        f"🔍  <b>ꜰɪʟᴛᴇʀ: {filter_label}</b>\n\nɴᴏᴡ ᴛʏᴘᴇ ʏᴏᴜʀ sᴇᴀʀᴄʜ ǫᴜᴇʀʏ:",
        reply_markup=back_btn("menu:search"),
        parse_mode="HTML",
    )


async def cbq_file_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    file_db_id = q.data.split(":")[2]

    doc = await FileService.get_by_id(file_db_id)
    if not doc:
        await q.answer("ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
        return

    import asyncio
    user_id = q.from_user.id
    is_fav = file_db_id in await _get_user_favs(user_id)
    asyncio.create_task(FileService.increment_views(file_db_id))
    asyncio.create_task(UserService.add_to_recent(user_id, file_db_id))

    icon = category_icon(doc.get("category", "other"))
    text = (
        f"{icon}  <b>{doc['file_name']}</b>\n\n"
        f"├ sɪᴢᴇ:      {format_size(doc.get('file_size', 0))}\n"
        f"├ ᴛʏᴘᴇ:      {doc.get('mime_type', '—')}\n"
        f"├ ᴄᴀᴛᴇɢᴏʀʏ: {doc.get('category', '—')}\n"
        f"├ ᴛᴀɢs:      {', '.join(doc.get('tags', [])) or '—'}\n"
        f"├ ᴅᴏᴡɴʟᴏᴀᴅs: {doc.get('downloads', 0)}\n"
        f"└ ᴜᴘʟᴏᴀᴅᴇᴅ: {doc['created_at'].strftime('%d %b %Y')}"
    )
    await q.edit_message_text(
        with_footer(text),
        reply_markup=file_actions(file_db_id, is_vault=doc.get("is_vault", False), is_favorite=is_fav),
        parse_mode="HTML",
    )


async def _get_user_favs(user_id: int) -> list:
    from services import UserService
    return await UserService.get_favorites(user_id)


async def _do_search_by_tag(update: Update, context: ContextTypes.DEFAULT_TYPE, tag_name: str) -> None:
    user_id = update.effective_user.id
    results, total = await SearchService.search(
        query="",
        owner_id=user_id,
        tags=[tag_name],
        page=0
    )
    total_pages = max(1, (total + cfg.SEARCH_PAGE_SIZE - 1) // cfg.SEARCH_PAGE_SIZE)
    
    if not results:
        text = (
            f"🔍  <b>ɴᴏ ʀᴇsᴜʟᴛs</b>\n\n"
            f"ɴᴏᴛʜɪɴɢ ꜰᴏᴜɴᴅ ꜰᴏʀ ᴛᴀɢ: <code>#{tag_name}</code>"
        )
        await update.callback_query.edit_message_text(with_footer(text), reply_markup=back_btn("menu:search"), parse_mode="HTML")
        return

    text = (
        f"🔍  <b>sᴇᴀʀᴄʜ ʀᴇsᴜʟᴛs</b>\n\n"
        f"ᴛᴀɢ: <code>#{tag_name}</code>\n"
        f"ꜰᴏᴜɴᴅ: <b>{total}</b> ꜰɪʟᴇ{'s' if total != 1 else ''}"
    )
    markup = search_results(results, f"#{tag_name}", page=0, total_pages=total_pages)
    await update.callback_query.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")


def get_handlers():
    return [
        CommandHandler("search", cmd_search),
        CallbackQueryHandler(cbq_search, pattern=r"^search:"),
        CallbackQueryHandler(cbq_filter, pattern=r"^filter:"),
        CallbackQueryHandler(cbq_file_view, pattern=r"^file:view:"),
    ]
