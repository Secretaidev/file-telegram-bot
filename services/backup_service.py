"""
vault bot — backup service
json export of all collections, scheduled auto-backup
"""

from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
from bson import ObjectId
from database import get_db

log = logging.getLogger(__name__)

BACKUP_DIR = "backups"


class _Encoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class BackupService:

    @staticmethod
    async def create_backup() -> str:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(BACKUP_DIR, f"backup_{ts}.json")

        db = get_db()
        collection_names = await db.list_collection_names()

        data: Dict[str, list] = {}
        for name in collection_names:
            cursor = db[name].find({})
            data[name] = await cursor.to_list(None)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=_Encoder, ensure_ascii=False, indent=2)

        size = os.path.getsize(path)
        log.info("backup created: %s (%.1f KB)", path, size / 1024)
        return path

    @staticmethod
    async def send_to_channels(bot, path: str) -> None:
        """Send the backup file to all configured backup channels."""
        from config import cfg
        if not cfg.BACKUP_CHANNEL_IDS:
            return
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        caption = f"💾 <b>ᴀᴜᴛᴏ ʙᴀᴄᴋᴜᴘ</b>\n<code>{ts}</code>"
        for chat_id in cfg.BACKUP_CHANNEL_IDS:
            try:
                with open(path, "rb") as f:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename=os.path.basename(path),
                        caption=caption,
                        parse_mode="HTML",
                    )
                log.info("backup sent to channel %d", chat_id)
            except Exception as e:
                log.error("failed to send backup to channel %d: %s", chat_id, e)

    @staticmethod
    async def restore_backup(path: str) -> Dict[str, int]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"backup not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        db = get_db()
        counts: Dict[str, int] = {}

        for collection_name, documents in data.items():
            if not documents:
                continue
            col = db[collection_name]
            await col.delete_many({})
            result = await col.insert_many(documents)
            counts[collection_name] = len(result.inserted_ids)

        log.info("backup restored from %s: %s", path, counts)
        return counts

    @staticmethod
    def list_backups() -> list:
        if not os.path.exists(BACKUP_DIR):
            return []
        files = []
        for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
            if f.endswith(".json"):
                full = os.path.join(BACKUP_DIR, f)
                files.append({
                    "name": f,
                    "path": full,
                    "size": os.path.getsize(full),
                    "created_at": datetime.fromtimestamp(os.path.getmtime(full)),
                })
        return files[:10]

    @staticmethod
    async def cleanup_old_backups(keep: int = 5) -> int:
        """Delete old local backup files, keeping only the most recent `keep` files."""
        backups = BackupService.list_backups()
        deleted = 0
        for b in backups[keep:]:
            try:
                os.remove(b["path"])
                deleted += 1
            except Exception as e:
                log.warning("failed to delete old backup %s: %s", b["path"], e)
        return deleted
