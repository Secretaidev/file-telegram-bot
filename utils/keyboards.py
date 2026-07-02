"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — inline keyboard builders
all ui built with inline keyboards; small caps unicode throughout
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from config import cfg

# ── monkey patch for colorful buttons ─────────────────────────────────────────

_button_styles = {}

_old_inline_to_dict = InlineKeyboardButton.to_dict

def _new_inline_to_dict(self, *args, **kwargs):
    d = _old_inline_to_dict(self, *args, **kwargs)
    style = _button_styles.pop(id(self), None)
    if style:
        d["style"] = style
    return d

InlineKeyboardButton.to_dict = _new_inline_to_dict


_old_kb_to_dict = KeyboardButton.to_dict

def _new_kb_to_dict(self, *args, **kwargs):
    d = _old_kb_to_dict(self, *args, **kwargs)
    style = _button_styles.pop(id(self), None)
    if style:
        d["style"] = style
    return d

KeyboardButton.to_dict = _new_kb_to_dict


# ── helpers ───────────────────────────────────────────────────────────────────

def btn(text: str, data: str, style: Optional[str] = None) -> InlineKeyboardButton:
    b = InlineKeyboardButton(text, callback_data=data)
    _button_styles[id(b)] = style or "primary"
    return b


def url_btn(text: str, url: str, style: Optional[str] = None) -> InlineKeyboardButton:
    b = InlineKeyboardButton(text, url=url)
    _button_styles[id(b)] = style or "primary"
    return b


def row(*buttons: InlineKeyboardButton) -> List[InlineKeyboardButton]:
    return list(buttons)


def build(*rows: List[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(list(rows))


# ── main menu ─────────────────────────────────────────────────────────────────

def main_menu(is_premium: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        row(btn("📁  ᴍʏ ꜰɪʟᴇs", "menu:files", "primary"), btn("🔍  sᴇᴀʀᴄʜ", "menu:search", "primary")),
        row(btn("📂  ꜰᴏʟᴅᴇʀs", "menu:folders", "primary"), btn("🔐  ᴠᴀᴜʟᴛ", "menu:vault", "primary")),
        row(btn("🔗  sʜᴀʀᴇ ʟɪɴᴋs", "menu:links", "primary"), btn("⭐  ꜰᴀᴠᴏʀɪᴛᴇs", "menu:favorites", "primary")),
        row(btn("📊  sᴛᴀᴛs", "menu:stats", "primary"), btn("💎  ᴘʀᴇᴍɪᴜᴍ", "menu:premium", "success")),
    ]
    if is_admin:
        rows.append(row(btn("⚙️  ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ", "admin:panel", "primary")))
    rows.append(row(btn("❓  ʜᴇʟᴘ", "menu:help", "primary"), btn("ℹ️  ᴀʙᴏᴜᴛ", "menu:about", "primary")))
    rows.append(row(
        url_btn("👨‍💻  ᴅᴇᴠ", "https://t.me/its_Xyron", "primary"),
        url_btn("🆘  sᴜᴘᴘᴏʀᴛ", "https://t.me/its_Xyron", "primary"),
    ))
    return build(*rows)


# ── file operations ───────────────────────────────────────────────────────────

def file_actions(file_id: str, is_vault: bool = False, is_favorite: bool = False) -> InlineKeyboardMarkup:
    fav_text = "💛  ᴜɴꜰᴀᴠ" if is_favorite else "⭐  ꜰᴀᴠᴏʀɪᴛᴇ"
    rows = [
        row(btn("📤  sᴇɴᴅ ꜰɪʟᴇ", f"file:send:{file_id}", "success"), btn(fav_text, f"file:fav:{file_id}", "primary")),
        row(btn("✏️  ʀᴇɴᴀᴍᴇ", f"file:rename:{file_id}", "primary"), btn("📋  ᴄᴏᴘʏ", f"file:copy:{file_id}", "primary")),
        row(btn("🔗  sʜᴀʀᴇ ʟɪɴᴋ", f"file:share:{file_id}", "primary"), btn("📁  ᴍᴏᴠᴇ", f"file:move:{file_id}", "primary")),
        row(btn("🤖  ᴀɪ ᴅᴇsᴄʀɪʙᴇ", f"file:aidesc:{file_id}", "success")),
        row(btn("🗑  ᴅᴇʟᴇᴛᴇ", f"file:delete:{file_id}", "danger"), btn("ℹ️  ɪɴꜰᴏ", f"file:info:{file_id}", "primary")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:files", "primary")),
    ]
    return build(*rows)


def file_delete_confirm(file_id: str) -> InlineKeyboardMarkup:
    return build(
        row(btn("✅  ʏᴇs, ᴅᴇʟᴇᴛᴇ", f"file:delete_confirm:{file_id}", "danger"),
            btn("❌  ᴄᴀɴᴄᴇʟ", f"file:view:{file_id}", "success")),
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
        rows.append(row(btn(f"📁  {f['name']}", f"folder:open:{f['_id']}", "success")))
    for f in files:
        rows.append(row(btn(f"📄  {f['file_name']}", f"file:view:{f['_id']}", "primary")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"folder:page:{current_id}:{page-1}", "primary"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop", "primary"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"folder:page:{current_id}:{page+1}", "primary"))
    if nav:
        rows.append(nav)

    actions = [btn("➕  ɴᴇᴡ ꜰᴏʟᴅᴇʀ", f"folder:new:{current_id or 'root'}", "success")]
    if current_id:
        actions.append(btn("📤  ᴜᴘʟᴏᴀᴅ ʜᴇʀᴇ", f"folder:upload:{current_id}", "success"))
    rows.append(actions)

    back_rows = []
    if parent_id:
        back_rows.append(btn("◀️  ᴜᴘ", f"folder:open:{parent_id}", "primary"))
    back_rows.append(btn("🏠  ʜᴏᴍᴇ", "menu:files", "primary"))
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
        rows.append(row(btn(f"📄  {r['file_name']}", f"file:view:{r['_id']}", "primary")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"search:page:{page-1}:{query}", "primary"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop", "primary"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"search:page:{page+1}:{query}", "primary"))
    if nav:
        rows.append(nav)

    sort_opts = [
        btn("🕐 ʟᴀᴛᴇsᴛ", f"search:sort:latest:{query}", "primary"),
        btn("📏 sɪᴢᴇ", f"search:sort:size:{query}", "primary"),
        btn("🔥 ᴘᴏᴘᴜʟᴀʀ", f"search:sort:popular:{query}", "primary"),
    ]
    rows.append(sort_opts)
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "menu:search", "primary")))
    return build(*rows)


def search_filters(pop_tags: list = None) -> InlineKeyboardMarkup:
    rows = [
        row(btn("📹  ᴠɪᴅᴇᴏs", "filter:video", "primary"), btn("🎵  ᴀᴜᴅɪᴏ", "filter:audio", "primary")),
        row(btn("📄  ᴅᴏᴄs", "filter:document", "primary"), btn("🖼  ᴘʜᴏᴛᴏs", "filter:photo", "primary")),
        row(btn("📦  ᴀʀᴄʜɪᴠᴇs", "filter:archive", "primary"), btn("🗂  ᴀʟʟ", "filter:all", "primary")),
    ]
    if pop_tags:
        tag_buttons = []
        for tag in pop_tags:
            tag_name = tag["_id"]
            tag_count = tag["count"]
            tag_buttons.append(btn(f"🏷  #{tag_name} ({tag_count})", f"search:tag:{tag_name}", "primary"))
        for i in range(0, len(tag_buttons), 2):
            rows.append(tag_buttons[i:i+2])
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "menu:start", "primary")))
    return build(*rows)


# ── premium ───────────────────────────────────────────────────────────────────

def premium_menu(has_premium: bool = False) -> InlineKeyboardMarkup:
    if has_premium:
        return build(
            row(btn("✅  ᴘʀᴇᴍɪᴜᴍ ᴀᴄᴛɪᴠᴇ", "noop", "success")),
            row(btn("📊  ᴍʏ ᴘʟᴀɴ", "premium:status", "primary")),
            row(btn("◀️  ʙᴀᴄᴋ", "menu:start", "primary")),
            row(
                url_btn("👨‍💻  ᴅᴇᴠ", "https://t.me/its_Xyron", "primary"),
                url_btn("🆘  sᴜᴘᴘᴏʀᴛ", "https://t.me/its_Xyron", "primary"),
            ),
        )
    return build(
        row(btn("👑  ᴍᴏɴᴛʜʟʏ — ₹9 / ᴍᴏɴᴛʜ", "premium:buy:monthly", "success")),
        row(btn("👑  ʏᴇᴀʀʟʏ — ₹99 / ʏᴇᴀʀ", "premium:buy:yearly", "success")),
        row(btn("💳  sᴇɴᴅ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ", "premium:payment", "success")),
        row(btn("📋  ᴘʟᴀɴ ᴄᴏᴍᴘᴀʀɪsᴏɴ", "premium:compare", "primary")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start", "primary")),
        row(
            url_btn("👨‍💻  ᴅᴇᴠ", "https://t.me/its_Xyron", "primary"),
            url_btn("🆘  sᴜᴘᴘᴏʀᴛ", "https://t.me/its_Xyron", "primary"),
        ),
    )


def payment_plan_select() -> InlineKeyboardMarkup:
    return build(
        row(btn("👑  ᴍᴏɴᴛʜʟʏ — ₹9 / ᴍᴏɴᴛʜ", "pay:plan:monthly:9", "success")),
        row(btn("👑  ʏᴇᴀʀʟʏ — ₹99 / ʏᴇᴀʀ", "pay:plan:yearly:99", "success")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:premium", "primary")),
    )




def payment_admin_review(payment_id: str) -> InlineKeyboardMarkup:
    return build(
        row(btn("✅  ᴀᴘᴘʀᴏᴠᴇ", f"pay:approve:{payment_id}", "success"),
            btn("❌  ʀᴇᴊᴇᴄᴛ", f"pay:reject:{payment_id}", "danger")),
    )


# ── vault ─────────────────────────────────────────────────────────────────────

def vault_menu() -> InlineKeyboardMarkup:
    return build(
        row(btn("📁  ᴍʏ ᴠᴀᴜʟᴛ ꜰɪʟᴇs", "vault:list", "primary"), btn("📤  ᴜᴘʟᴏᴀᴅ ᴛᴏ ᴠᴀᴜʟᴛ", "vault:upload", "success")),
        row(btn("🔒  ʟᴏᴄᴋ ᴠᴀᴜʟᴛ", "vault:lock", "danger"), btn("🔑  ᴄʜᴀɴɢᴇ ᴘɪɴ", "vault:change_pin", "primary")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start", "primary")),
    )


def vault_unlock() -> InlineKeyboardMarkup:
    return build(
        row(btn("🔑  ᴇɴᴛᴇʀ ᴘɪɴ", "vault:enter_pin", "success")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:start", "primary")),
    )


# ── share links ───────────────────────────────────────────────────────────────

def share_options(file_db_id: str) -> InlineKeyboardMarkup:
    return build(
        row(btn("⏱  1 ʜᴏᴜʀ", f"share:create:{file_db_id}:1h", "primary"),
            btn("📅  1 ᴅᴀʏ", f"share:create:{file_db_id}:24h", "primary")),
        row(btn("📆  7 ᴅᴀʏs", f"share:create:{file_db_id}:168h", "primary"),
            btn("♾  ɴᴏ ᴇxᴘɪʀʏ", f"share:create:{file_db_id}:0h", "primary")),
        row(btn("1️⃣  ᴏɴᴇ-ᴛɪᴍᴇ ʟɪɴᴋ", f"share:onetime:{file_db_id}", "success")),
        row(btn("◀️  ʙᴀᴄᴋ", f"file:view:{file_db_id}", "primary")),
    )


def share_link_view(token: str, link_id: str) -> InlineKeyboardMarkup:
    from utils.helpers import start_link
    return build(
        row(url_btn("🔗  ᴏᴘᴇɴ ʟɪɴᴋ", start_link(f"dl_{token}"), "success")),
        row(btn("🗑  ʀᴇᴠᴏᴋᴇ ʟɪɴᴋ", f"share:revoke:{link_id}", "danger")),
        row(btn("◀️  ʙᴀᴄᴋ", "menu:links", "primary")),
    )


# ── admin ─────────────────────────────────────────────────────────────────────

def admin_panel() -> InlineKeyboardMarkup:
    return build(
        row(btn("👥  ᴜsᴇʀs", "admin:users", "primary"), btn("📊  sᴛᴀᴛs", "admin:stats", "primary")),
        row(btn("📢  ʙʀᴏᴀᴅᴄᴀsᴛ", "admin:broadcast", "primary"), btn("💳  ᴘᴀʏᴍᴇɴᴛs", "admin:payments", "success")),
        row(btn("📋  ʟᴏɢs", "admin:logs:0", "primary"), btn("🔎  sᴇᴀʀᴄʜ ᴜsᴇʀ", "admin:searchuser", "primary")),
        row(btn("🛠  ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ", "admin:maintenance", "danger"), btn("💾  ʙᴀᴄᴋᴜᴘ", "admin:backup", "primary")),
        row(btn("📂  ʙᴀᴄᴋᴜᴘ ʟɪsᴛ", "admin:backuplist", "primary"), btn("◀️  ʙᴀᴄᴋ", "menu:start", "primary")),
    )


def admin_user_actions(user_id: int, is_banned: bool, is_premium: bool) -> InlineKeyboardMarkup:
    ban_text = "✅  ᴜɴʙᴀɴ" if is_banned else "🚫  ʙᴀɴ"
    ban_style = "success" if is_banned else "danger"
    prem_text = "❌  ʀᴇᴠᴏᴋᴇ ᴘʀᴇᴍɪᴜᴍ" if is_premium else "💎  ɢʀᴀɴᴛ ᴘʀᴇᴍɪᴜᴍ"
    prem_style = "danger" if is_premium else "success"
    return build(
        row(btn(ban_text, f"admin:toggleban:{user_id}", ban_style),
            btn(prem_text, f"admin:togglepremium:{user_id}", prem_style)),
        row(btn("📊  ᴜsᴇʀ sᴛᴀᴛs", f"admin:userstats:{user_id}", "primary"),
            btn("🗑  ᴅᴇʟᴇᴛᴇ ꜰɪʟᴇs", f"admin:deletefiles:{user_id}", "danger")),
        row(btn("📋  ᴜsᴇʀ ʟᴏɢs", f"admin:userlogs:{user_id}:0", "primary")),
        row(btn("◀️  ʙᴀᴄᴋ", "admin:users", "primary")),
    )


def pending_payments_list(payments: list) -> InlineKeyboardMarkup:
    rows = []
    for p in payments:
        rows.append(row(btn(
            f"💳 {p['user_id']} — {p['plan']} — ₹{p['amount']}",
            f"admin:reviewpay:{str(p['_id'])}",
            "success"
        )))
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "admin:panel", "primary")))
    return build(*rows)


def backup_list_kb(backups: list) -> InlineKeyboardMarkup:
    rows = []
    for b in backups:
        from utils.helpers import format_size
        size_str = format_size(b["size"])
        label = f"💾 {b['name'][:20]}{'…' if len(b['name']) > 20 else ''} ({size_str})"
        rows.append(row(btn(label, f"admin:backupdownload:{b['name']}", "primary")))
    rows.append(row(btn("◀️  ʙᴀᴄᴋ", "admin:panel", "primary")))
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
        rows.append(row(btn(label, f"{prefix}:{item['_id']}", "primary")))

    nav = []
    if page > 0:
        nav.append(btn("◀️", f"{prefix}_page:{page-1}", "primary"))
    nav.append(btn(f"{page+1}/{total_pages}", "noop", "primary"))
    if page < total_pages - 1:
        nav.append(btn("▶️", f"{prefix}_page:{page+1}", "primary"))
    if nav:
        rows.append(nav)

    rows.append(row(btn("◀️  ʙᴀᴄᴋ", back_data, "primary")))
    return chunk, build(*rows)


# ── misc ──────────────────────────────────────────────────────────────────────

def back_btn(data: str = "menu:start") -> InlineKeyboardMarkup:
    return build(row(btn("◀️  ʙᴀᴄᴋ", data, "primary")))


def close_btn() -> InlineKeyboardMarkup:
    return build(row(btn("✖️  ᴄʟᴏsᴇ", "close", "danger")))


def join_channels(channels: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [row(url_btn(f"📢  ᴊᴏɪɴ @{username}", url, "primary")) for username, url in channels]
    rows.append(row(btn("✅  ɪ'ᴠᴇ ᴊᴏɪɴᴇᴅ", "check:joined", "success")))
    return build(*rows)


def noop_markup() -> InlineKeyboardMarkup:
    return build(row(btn("·", "noop", "primary")))
