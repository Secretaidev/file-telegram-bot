"""
vault bot — general helpers
"""

from __future__ import annotations
import hashlib
import secrets
import mimetypes
from datetime import datetime
from typing import Optional
from database.models import FileCategory
from config import cfg


# ── formatting ────────────────────────────────────────────────────────────────

def format_size(size_bytes: int) -> str:
    for unit in ("ʙ", "ᴋʙ", "ᴍʙ", "ɢʙ"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} ᴛʙ"


def format_dt(dt: datetime) -> str:
    return dt.strftime("%d %b %Y, %H:%M UTC")


def time_left(dt: datetime) -> str:
    diff = dt - datetime.utcnow()
    seconds = int(diff.total_seconds())
    if seconds <= 0:
        return "ᴇxᴘɪʀᴇᴅ"
    if seconds < 3600:
        return f"{seconds // 60}ᴍ {seconds % 60}s"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h}ʜ {(seconds % 3600) // 60}ᴍ"
    d = seconds // 86400
    return f"{d}ᴅ {(seconds % 86400) // 3600}ʜ"


# ── tokens & hashes ───────────────────────────────────────────────────────────

def generate_token(length: int = 16) -> str:
    return secrets.token_urlsafe(length)


def hash_file_id(unique_id: str) -> str:
    return hashlib.sha256(unique_id.encode()).hexdigest()[:32]


def hash_pin(pin: str) -> str:
    salt = cfg.VAULT_SECRET[:8]
    return hashlib.sha256(f"{salt}{pin}".encode()).hexdigest()


# ── mime / category ───────────────────────────────────────────────────────────

_CATEGORY_MAP = {
    "video":       FileCategory.VIDEO,
    "audio":       FileCategory.AUDIO,
    "image":       FileCategory.PHOTO,
    "application/pdf":          FileCategory.DOCUMENT,
    "application/zip":          FileCategory.ARCHIVE,
    "application/x-rar":        FileCategory.ARCHIVE,
    "application/x-tar":        FileCategory.ARCHIVE,
    "application/x-7z":         FileCategory.ARCHIVE,
    "application/msword":       FileCategory.DOCUMENT,
    "application/vnd.openxmlformats": FileCategory.DOCUMENT,
    "text/":                    FileCategory.DOCUMENT,
}


def get_category(mime_type: str) -> FileCategory:
    for key, cat in _CATEGORY_MAP.items():
        if mime_type.startswith(key):
            return cat
    return FileCategory.OTHER


def category_icon(category: str) -> str:
    icons = {
        "video":    "🎬",
        "audio":    "🎵",
        "photo":    "🖼",
        "document": "📄",
        "archive":  "📦",
        "other":    "📎",
    }
    return icons.get(category, "📎")


def safe_filename(name: str, max_len: int = 64) -> str:
    bad = r'\/:*?"<>|'
    for c in bad:
        name = name.replace(c, "_")
    return name.strip()[:max_len] or "unnamed_file"


# ── smart naming ──────────────────────────────────────────────────────────────

def suggest_name(original: str, mime_type: str) -> str:
    ext = mimetypes.guess_extension(mime_type) or ""
    base = original.rsplit(".", 1)[0] if "." in original else original
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{base}_{ts}{ext}"


# ── upi payment link ──────────────────────────────────────────────────────────

def upi_link(amount: float, note: str = "vault premium") -> str:
    return (
        f"upi://pay?pa={cfg.UPI_ID}"
        f"&pn={cfg.UPI_NAME.replace(' ', '%20')}"
        f"&am={amount}"
        f"&tn={note.replace(' ', '%20')}"
        f"&cu=INR"
    )


def gpay_link(amount: float, note: str = "vault premium") -> str:
    return upi_link(amount, note)


# ── deep link ─────────────────────────────────────────────────────────────────

def start_link(payload: str) -> str:
    return f"https://t.me/{cfg.BOT_USERNAME}?start={payload}"


# ── footer ────────────────────────────────────────────────────────────────────

FOOTER = f"\n\n<i>{cfg.FOOTER}</i>"


def with_footer(text: str) -> str:
    return text + FOOTER
