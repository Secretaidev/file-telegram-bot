"""
vault bot — folder handler
create, navigate, rename, delete folder tree
"""

from __future__ import annotations
import logging
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from middlewares import auth_middleware
from services import FolderService, FileService
from utils import folder_list, with_footer, format_size, back_btn, channel_log, btn, row, build
from config import cfg

log = logging.getLogger(__name__)


async def cbq_folder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    user_id = q.from_user.id

    if action == "open":
        folder_id = parts[2] if parts[2] != "root" else None
        page = int(parts[3]) if len(parts) > 3 else 0
        await q.answer()
        await _show_folder(q, context, user_id, folder_id, page)

    elif action == "page":
        folder_id = parts[2] if parts[2] != "null" else None
        page = int(parts[3])
        await q.answer()
        await _show_folder(q, context, user_id, folder_id, page)

    elif action == "new":
        parent_raw = parts[2]
        parent_id = None if parent_raw == "root" else parent_raw
        context.user_data["creating_folder"] = parent_id
        await q.answer()
        await q.edit_message_text(
            with_footer("📂  <b>ɴᴇᴡ ꜰᴏʟᴅᴇʀ</b>\n\nsᴇɴᴅ ᴀ ɴᴀᴍᴇ ꜰᴏʀ ᴛʜᴇ ꜰᴏʟᴅᴇʀ:"),
            reply_markup=back_btn("menu:folders"),
            parse_mode="HTML",
        )

    elif action == "upload":
        folder_id = parts[2]
        context.user_data["upload_folder_id"] = folder_id
        await q.answer()
        await q.edit_message_text(
            with_footer("📤  sᴇɴᴅ ᴀ ꜰɪʟᴇ ᴛᴏ ᴜᴘʟᴏᴀᴅ ɪɴᴛᴏ ᴛʜɪs ꜰᴏʟᴅᴇʀ:"),
            reply_markup=back_btn(f"folder:open:{folder_id}"),
            parse_mode="HTML",
        )

    elif action == "delete":
        folder_id = parts[2]
        folder = await FolderService.get_by_id(folder_id)
        if not folder or folder["owner_id"] != user_id:
            await q.answer("ɴᴏᴛ ꜰᴏᴜɴᴅ.", show_alert=True)
            return
        await q.answer()
        await q.edit_message_text(
            with_footer(
                f"🗑  <b>ᴅᴇʟᴇᴛᴇ ꜰᴏʟᴅᴇʀ</b>\n\n"
                f"ᴅᴇʟᴇᴛᴇ '<b>{folder['name']}</b>' ᴀɴᴅ ᴀʟʟ ᴄᴏɴᴛᴇɴᴛs?"
            ),
            reply_markup=build(
                row(btn("✅  ʏᴇs", f"folder:delete_confirm:{folder_id}"),
                    btn("❌  ɴᴏ", f"folder:open:{folder_id}")),
            ),
            parse_mode="HTML",
        )

    elif action == "delete_confirm":
        folder_id = parts[2]
        ok = await FolderService.delete(folder_id, user_id)
        await q.answer("✅ ᴅᴇʟᴇᴛᴇᴅ." if ok else "❌ ꜰᴀɪʟᴇᴅ.", show_alert=True)
        await _show_folder(q, context, user_id, None, 0)


async def _show_folder(q, context, user_id: int, folder_id, page: int = 0) -> None:
    sub_folders = await FolderService.list_children(user_id, folder_id)
    folder_files, total_files = await FolderService.list_files_in(user_id, folder_id, page)
    total_pages = max(1, (total_files + cfg.PAGE_SIZE - 1) // cfg.PAGE_SIZE)

    if folder_id:
        folder = await FolderService.get_by_id(folder_id)
        parent_id = folder.get("parent_id") if folder else None
        title = folder["name"] if folder else "ꜰᴏʟᴅᴇʀ"
    else:
        parent_id = None
        title = "ᴍʏ ꜰɪʟᴇs"

    breadcrumb = await FolderService.breadcrumb(folder_id)
    crumb_str = " › ".join(f["name"] for f in breadcrumb) if breadcrumb else "ʀᴏᴏᴛ"

    text = (
        f"📁  <b>{title}</b>\n"
        f"<i>{crumb_str}</i>\n\n"
        f"ꜰᴏʟᴅᴇʀs: {len(sub_folders)} · ꜰɪʟᴇs: {total_files}"
    )
    markup = folder_list(
        folders=sub_folders,
        files=folder_files,
        parent_id=parent_id,
        current_id=folder_id,
        page=page,
        total_pages=total_pages,
    )
    await q.edit_message_text(with_footer(text), reply_markup=markup, parse_mode="HTML")


async def handle_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if "creating_folder" not in context.user_data:
        return
    parent_id = context.user_data.pop("creating_folder")
    name = update.message.text.strip()[:40]
    user_id = update.effective_user.id

    if not name:
        await update.message.reply_text("❌ ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ᴀ ᴠᴀʟɪᴅ ɴᴀᴍᴇ.")
        return

    folder = await FolderService.create(name=name, owner_id=user_id, parent_id=parent_id)
    folder_id = str(folder["_id"])

    markup = build(
        row(btn("📂  ᴏᴘᴇɴ ꜰᴏʟᴅᴇʀ", f"folder:open:{folder_id}"),
            btn("◀️  ʙᴀᴄᴋ", "menu:files")),
    )
    await update.message.reply_text(
        with_footer(f"✅  ꜰᴏʟᴅᴇʀ '<b>{name}</b>' ᴄʀᴇᴀᴛᴇᴅ."),
        reply_markup=markup,
        parse_mode="HTML",
    )


def get_handlers():
    return [
        CallbackQueryHandler(cbq_folder, pattern=r"^folder:"),
    ]
