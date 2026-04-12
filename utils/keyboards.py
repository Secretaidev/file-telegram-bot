"""
vault bot — inline keyboard builders
all ui built with inline keyboards; small caps unicode throughout
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import cfg


# ── helpers ───────────────────────────────────────────────────────────────────

def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url)


def row(*buttons: InlineKeyboardButton) -> List[InlineKeyboardButton]:
    return list(buttons)


def build(*rows: List[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(list(rows))


# ── main menu ─────────────────────────────────────────────────────────────────

def main_menu(is_premium: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        row(btn("📁  ᴍʏ ꜰɪʟᴇs", "menu:files"), btn("🔍  sᴇᴀʀᴄʜ", "menu:search")),
        row(btn("📂  ꜰᴏʟᴅᴇʀs", "menu:folders"), btn("🔐  ᴠᴀᴜʟᴛ", "menu:vault")),
        row(btn("🔗  sʜᴀʀᴇ ʟɪɴᴋs", "menu:links"), btn("⭐  ꜰᴀᴠᴏʀɪᴛᴇs", "menu:favorites")),
        row(btn("📊  sᴛᴀᴛs", "menu:stats"), btn("💎  ᴘʀᴇᴍɪᴜᴍ", "menu:premium")),
    ]
    if is_admin:
        rows.append(row(btn("⚙️  ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", "admin:panel")))
    rows.append(row(btn("❓  ʜᴇʟᴘ", "menu:help"), btn("ℹ️  ᴀʙᴏᴜᴛ", "menu:about")))
    return build(*rows)


# ── file operations ───────────────────────────────────────────────────────────

def file_actions(file_id: str, is_vault: bool = False, is_favorite: bool = False) -> InlineKeyboardMarkup:
    fav_text = "💛  ᴜɴꜰᴀᴠ" if is_favorite else "⭐  ꜰᴀᴠᴏʀɪᴛᴇ"
    rows = [
        row(btn("📤  sᴇɴᴅ ꜰɪʟᴇ", f"file:send:{file_id}"), btn(fav_text, f"file:fav:{file_id}")),
        row(btn("✏️  ʀᴇɴᴀᴍᴇ", f"file:rename:{file_id}"), btn("📋  ᴄᴏᴘʏ", f"file:copy:{file_id}")),
        row(btn("🔗  sʜᴀʀᴇ ʟɪɴᴋ", f"file:share:{file_id}"), btn("📁  ᴍᴏᴠᴇ", f"file:move:{file_id}")),
        row(btn("🗑  ᴅᴇʟᴇᴛᴇ", f"file:delete:{file_id}"), btn("ℹ️  ɪɴꜰᴏ", f"file:info:{file_id}")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:files")),
    ]
    return build(*rows)


def file_delete_confirm(file_id: str) -> InlineKeyboardMarkup:
    return build(
        row(btn("✅  ʏᴇs, ᴅᴇʟᴇᴛᴇ", f"file:delete_confirm:{file_id}"),
            btn("❌  ᴄᴀɴᴄᴇʟ", f"file:view:{file_id}")),
    )


# ── folder navigation ─────────────────────────────────────────────────────────

def folder_list(
    folders: list,
    files: list,
    parent_id: Optional[str],
    current_id: Optional[str],
    page: int = 0,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    rows = []
    for f in folders:
        rows.append(row(btn(f"📁  {f['name']}", f"folder:open:{f['_id']}")))
    for f in files:
        rows.append(row(btn(f"📄  {f['file_name']}", f"file:view:{f['_id']}")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"folder:page:{current_id}:{page-1}"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"folder:page:{current_id}:{page+1}"))
    if nav:
        rows.append(nav)

    actions = [btn("➕  ɴᴇᴡ ꜰᴏʟᴅᴇʀ", f"folder:new:{current_id or 'root'}")]
    if current_id:
        actions.append(btn("📤  ᴜᴘʟᴏᴀᴅ ʜᴇʀᴇ", f"folder:upload:{current_id}"))
    rows.append(actions)

    back_rows = []
    if parent_id:
        back_rows.append(btn("◀️  ᴜᴘ", f"folder:open:{parent_id}"))
    back_rows.append(btn("🏠  ʜᴏᴍᴇ", "menu:files"))
    rows.append(back_rows)

    return build(*rows)


# ── search ────────────────────────────────────────────────────────────────────

def search_results(
    results: list,
    query: str,
    page: int,
    total_pages: int,
    sort_by: str = "latest",
) -> InlineKeyboardMarkup:
    rows = []
    for r in results:
        rows.append(row(btn(f"📄  {r['file_name']}", f"file:view:{r['_id']}")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"search:page:{page-1}:{query}"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"search:page:{page+1}:{query}"))
    if nav:
        rows.append(nav)

    sort_opts = [
        btn("🕐 ʟᴀᴛᴇsᴛ", f"search:sort:latest:{query}"),
        btn("📏 sɪᴢᴇ", f"search:sort:size:{query}"),
        btn("🔥 ᴘᴏᴘᴜʟᴀʀ", f"search:sort:popular:{query}"),
    ]
    rows.append(sort_opts)
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "menu:search")))
    return build(*rows)


def search_filters() -> InlineKeyboardMarkup:
    return build(
        row(btn("📹  ᴠɪᴅᴇᴏs", "filter:video"), btn("🎵  ᴀᴜᴅɪᴏ", "filter:audio")),
        row(btn("📄  ᴅᴏᴄs", "filter:document"), btn("🖼  ᴘʜᴏᴛᴏs", "filter:photo")),
        row(btn("📦  ᴀʀᴄʜɪᴠᴇs", "filter:archive"), btn("🗂  ᴀʟʟ", "filter:all")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:search")),
    )


# ── premium ───────────────────────────────────────────────────────────────────

def premium_menu(has_premium: bool = False) -> InlineKeyboardMarkup:
    if has_premium:
        return build(
            row(btn("✅  ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴇ", "noop")),
            row(btn("📊  ᴍʏ ᴘʟᴀɴ", "premium:status")),
            row(btn("◀️  ʙᴀᴄᴋ", "menu:start")),
        )
    return build(
        row(btn("👑  ʏᴇᴀʀʟʏ — ₹39/ʏᴇᴀʀ", "premium:buy:yearly")),
        row(btn("💳  sᴇɴᴅ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ", "premium:payment")),
        row(btn("📋  ᴘʟᴀɴ ᴄᴏᴍᴘᴀʀɪsᴏɴ", "premium:compare")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start")),
    )


def payment_plan_select() -> InlineKeyboardMarkup:
    return build(
        row(btn("👑  ʏᴇᴀʀʟʏ — ₹39/ʏᴇᴀʀ", "pay:plan:yearly:39")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:premium")),
    )


def payment_admin_review(payment_id: str) -> InlineKeyboardMarkup:
    return build(
        row(btn("✅  ᴀᴘᴘʀᴏᴠᴇ", f"pay:approve:{payment_id}"),
            btn("❌  ʀᴇᴊᴇᴄᴛ", f"pay:reject:{payment_id}")),
    )


# ── vault ─────────────────────────────────────────────────────────────────────

def vault_menu() -> InlineKeyboardMarkup:
    return build(
        row(btn("📁  ᴍʏ ᴠᴀᴜʟᴛ ꜰɪʟᴇs", "vault:list"), btn("📤  ᴜᴘʟᴏᴀᴅ ᴛᴏ ᴠᴀᴜʟᴛ", "vault:upload")),
        row(btn("🔒  ʟᴏᴄᴋ ᴠᴀᴜʟᴛ", "vault:lock"), btn("🔑  ᴄʜᴀɴɢᴇ ᴘɪɴ", "vault:change_pin")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start")),
    )


def vault_unlock() -> InlineKeyboardMarkup:
    return build(
        row(btn("🔑  ᴇɴᴛᴇʀ ᴘɪɴ", "vault:enter_pin")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start")),
    )


# ── share links ───────────────────────────────────────────────────────────────

def share_options(file_db_id: str) -> InlineKeyboardMarkup:
    return build(
        row(btn("⏱  1 ʜᴏᴜʀ", f"share:create:{file_db_id}:1h"),
            btn("📅  1 ᴅᴀʏ", f"share:create:{file_db_id}:24h")),
        row(btn("📆  7 ᴅᴀʏs", f"share:create:{file_db_id}:168h"),
            btn("♾  ɴᴏ ᴇxᴘɪʀʏ", f"share:create:{file_db_id}:0h")),
        row(btn("1️⃣  ᴏɴᴇ-ᴛɪᴍᴇ ʟɪɴᴋ", f"share:onetime:{file_db_id}")),
        row(btn("◀️  ʙᴀᴄᴋ", f"file:view:{file_db_id}")),
    )


def share_link_view(token: str, link_id: str) -> InlineKeyboardMarkup:
    from utils.helpers import start_link
    return build(
        row(url_btn("🔗  ᴏᴘᴇɴ ʟɪɴᴋ", start_link(f"dl_{token}"))),
        row(btn("🗑  ʀᴇᴠᴏᴋᴇ ʟɪɴᴋ", f"share:revoke:{link_id}")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:links")),
    )


# ── admin ─────────────────────────────────────────────────────────────────────

def admin_panel() -> InlineKeyboardMarkup:
    return build(
        row(btn("👥  ᴜsᴇʀs", "admin:users"), btn("📊  sᴛᴀᴛs", "admin:stats")),
        row(btn("📢  ʙʀᴏᴀᴅᴄᴀsᴛ", "admin:broadcast"), btn("💳  ᴘᴀʏᴍᴇɴᴛs", "admin:payments")),
        row(btn("📋  ʟᴏɢs", "admin:logs:0"), btn("🔎  sᴇᴀʀᴄʜ ᴜsᴇʀ", "admin:searchuser")),
        row(btn("🛠  ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ", "admin:maintenance"), btn("💾  ʙᴀᴄᴋᴜᴘ", "admin:backup")),
        row(btn("📂  ʙᴀᴄᴋᴜᴘ ʟɪsᴛ", "admin:backuplist"), btn("◀️  ʙᴀᴄᴋ", "menu:start")),
    )


def admin_user_actions(user_id: int, is_banned: bool, is_premium: bool) -> InlineKeyboardMarkup:
    ban_text = "✅  ᴜɴʙᴀɴ" if is_banned else "🚫  ʙᴀɴ"
    prem_text = "❌  ʀᴇᴠᴏᴋᴇ ᴘʀᴇᴍɪᴜᴍ" if is_premium else "💎  ɢʀᴀɴᴛ ᴘʀᴇᴍɪᴜᴍ"
    return build(
        row(btn(ban_text, f"admin:toggleban:{user_id}"),
            btn(prem_text, f"admin:togglepremium:{user_id}")),
        row(btn("📊  ᴜsᴇʀ sᴛᴀᴛs", f"admin:userstats:{user_id}"),
            btn("🗑  ᴅᴇʟᴇᴛᴇ ꜰɪʟᴇs", f"admin:deletefiles:{user_id}")),
        row(btn("📋  ᴜsᴇʀ ʟᴏɢs", f"admin:userlogs:{user_id}:0")),
        row(btn("◀️  ʙᴀᴄᴋ", "admin:users")),
    )


def pending_payments_list(payments: list) -> InlineKeyboardMarkup:
    rows = []
    for p in payments:
        rows.append(row(btn(
            f"💳 {p['user_id']} — {p['plan']} — ₹{p['amount']}",
            f"admin:reviewpay:{str(p['_id'])}"
        )))
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "admin:panel")))
    return build(*rows)


def backup_list_kb(backups: list) -> InlineKeyboardMarkup:
    rows = []
    for b in backups:
        from utils.helpers import format_size
        size_str = format_size(b["size"])
        label = f"💾 {b['name'][:20]}{'…' if len(b['name']) > 20 else ''} ({size_str})"
        rows.append(row(btn(label, f"admin:backupdownload:{b['name']}")))
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "admin:panel")))
    return build(*rows)


# ── pagination helper ─────────────────────────────────────────────────────────

def paginate(
    items: list,
    page: int,
    prefix: str,
    back_data: str,
    item_label_fn=None,
    page_size: int = 5,
) -> Tuple[list, InlineKeyboardMarkup]:
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    chunk = items[page * page_size:(page + 1) * page_size]

    rows = []
    for item in chunk:
        label = item_label_fn(item) if item_label_fn else str(item)
        rows.append(row(btn(label, f"{prefix}:{item['_id']}")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"{prefix}_page:{page-1}"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"{prefix}_page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append(row(btn("◀️  ʙᴀᴄᴋ", back_data)))
    return chunk, build(*rows)


# ── misc ──────────────────────────────────────────────────────────────────────

def back_btn(data: str = "menu:start") -> InlineKeyboardMarkup:
    return build(row(btn("◀️  ʙᴀᴄᴋ", data)))


def close_btn() -> InlineKeyboardMarkup:
    return build(row(btn("✖️  ᴄʟᴏsᴇ", "close")))


def join_channels(channels: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [row(url_btn(f"📢  ᴊᴏɪɴ @{username}", url)) for username, url in channels]
    rows.append(row(btn("✅  ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ", "check:joined")))
    return build(*rows)


def noop_markup() -> InlineKeyboardMarkup:
    return build(row(btn("·", "noop")))
