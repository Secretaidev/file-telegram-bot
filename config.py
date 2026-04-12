"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — central configuration
loads and validates all environment variables at startup
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"missing required env var: {key}")
    return val


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _list(key: str, sep: str = ",") -> List[str]:
    val = os.getenv(key, "")
    return [x.strip() for x in val.split(sep) if x.strip()]


def _list_int(key: str, sep: str = ",") -> List[int]:
    return [int(x) for x in _list(key, sep)]


def _storage_limit_bytes(key: str, default_mb: int) -> int:
    """Return storage limit in bytes. 0 means unlimited."""
    mb = _int(key, default_mb)
    return 0 if mb == 0 else mb * 1024 * 1024


@dataclass(frozen=True)
class Config:
    # core
    BOT_TOKEN: str = field(default_factory=lambda: _require("BOT_TOKEN"))
    OWNER_ID: int = field(default_factory=lambda: _int("OWNER_ID", 0))
    ADMIN_IDS: List[int] = field(default_factory=lambda: _list_int("ADMIN_IDS"))
    BOT_USERNAME: str = field(default_factory=lambda: os.getenv("BOT_USERNAME", "secretfilestoragebot"))

    # database
    MONGO_URI: str = field(default_factory=lambda: _require("MONGO_URI"))
    DB_NAME: str = field(default_factory=lambda: os.getenv("DB_NAME", "secretfilebot"))

    # channels
    STORAGE_CHANNEL_ID: int = field(default_factory=lambda: _int("STORAGE_CHANNEL_ID", 0))
    # multi-channel storage: files are distributed across all of these channels
    # if empty, falls back to STORAGE_CHANNEL_ID alone
    STORAGE_CHANNEL_IDS: List[int] = field(default_factory=lambda: _list_int("STORAGE_CHANNEL_IDS"))
    LOG_CHANNEL_ID: int = field(default_factory=lambda: _int("LOG_CHANNEL_ID", 0))
    REQUIRED_CHANNELS: List[str] = field(default_factory=lambda: _list("REQUIRED_CHANNELS"))
    # backup channels: send backup JSON to these telegram chat IDs (comma-separated)
    BACKUP_CHANNEL_IDS: List[int] = field(default_factory=lambda: _list_int("BACKUP_CHANNEL_IDS"))

    # security
    VAULT_SECRET: str = field(default_factory=lambda: os.getenv("VAULT_SECRET", "default_secret_change_me_123456"))
    RATE_LIMIT_MESSAGES: int = field(default_factory=lambda: _int("RATE_LIMIT_MESSAGES", 10))
    RATE_LIMIT_WINDOW: int = field(default_factory=lambda: _int("RATE_LIMIT_WINDOW", 60))
    SESSION_TIMEOUT: int = field(default_factory=lambda: _int("SESSION_TIMEOUT", 1800))

    # storage limits (bytes); 0 = unlimited
    FREE_STORAGE_LIMIT: int = field(default_factory=lambda: _storage_limit_bytes("FREE_STORAGE_LIMIT_MB", 500))
    PREMIUM_STORAGE_LIMIT: int = field(default_factory=lambda: _storage_limit_bytes("PREMIUM_STORAGE_LIMIT_MB", 0))
    FREE_UPLOAD_LIMIT: int = field(default_factory=lambda: _storage_limit_bytes("FREE_UPLOAD_LIMIT_MB", 20))
    PREMIUM_UPLOAD_LIMIT: int = field(default_factory=lambda: _storage_limit_bytes("PREMIUM_UPLOAD_LIMIT_MB", 2048))

    # payment
    UPI_ID: str = field(default_factory=lambda: os.getenv("UPI_ID", "yourname@gpay"))
    UPI_NAME: str = field(default_factory=lambda: os.getenv("UPI_NAME", "Secret File Storage Bot"))

    # backup
    BACKUP_INTERVAL_HOURS: int = field(default_factory=lambda: _int("BACKUP_INTERVAL_HOURS", 48))

    # AI (Grok / xAI)
    GROK_API_KEY: str = field(default_factory=lambda: os.getenv("GROK_API_KEY", ""))

    # pagination
    PAGE_SIZE: int = 5
    SEARCH_PAGE_SIZE: int = 8

    # bot identity
    BOT_NAME: str = "sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ"

    # footer
    FOOTER: str = "ᴅᴇᴠ: @its_me_secret | sᴜᴘᴘᴏʀᴛ: @song_assistant"

    def is_admin(self, user_id: int) -> bool:
        return user_id == self.OWNER_ID or user_id in self.ADMIN_IDS

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.OWNER_ID

    def all_storage_channels(self) -> List[int]:
        """Return all storage channel IDs, falling back to STORAGE_CHANNEL_ID."""
        channels = list(self.STORAGE_CHANNEL_IDS)
        if self.STORAGE_CHANNEL_ID and self.STORAGE_CHANNEL_ID not in channels:
            channels.append(self.STORAGE_CHANNEL_ID)
        return channels or ([self.STORAGE_CHANNEL_ID] if self.STORAGE_CHANNEL_ID else [])


cfg = Config()
