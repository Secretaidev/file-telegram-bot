"""
vault bot — file service
all file crud, versioning, duplicate detection
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from telegram import Message
from database import files, users, file_doc, FileCategory
from database.models import file_doc as mk_file
from utils.helpers import hash_file_id, get_category, safe_filename, suggest_name
from cachetools import TTLCache
from config import cfg

log = logging.getLogger(__name__)

# Bounded in-memory cache for frequently accessed file details (avoids redundant MongoDB lookups)
_file_cache: TTLCache[str, Dict[str, Any]] = TTLCache(maxsize=5000, ttl=300)


class FileService:

    # ── upload / create ───────────────────────────────────────────────────────

    @staticmethod
    async def save_file(
        message: Message,
        owner_id: int,
        folder_id: Optional[str] = None,
        is_vault: bool = False,
        tags: Optional[List[str]] = None,
        storage_msg_id: Optional[int] = None,
        storage_channel_id: int = 0,
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        saves a telegram file to the database.
        returns (doc, is_duplicate).
        """
        attachment = (
            message.document
            or message.video
            or message.audio
            or (message.photo[-1] if message.photo else None)
            or message.voice
            or message.video_note
            or message.sticker
        )
        if not attachment:
            return None, False

        file_id = attachment.file_id
        unique_id = attachment.file_unique_id
        file_hash = hash_file_id(unique_id)

        # duplicate check
        existing = await files().find_one({"file_hash": file_hash, "owner_id": owner_id, "is_deleted": False})
        if existing:
            return existing, True

        if message.document:
            name = message.document.file_name or "document"
            mime = message.document.mime_type or "application/octet-stream"
            size = message.document.file_size or 0
        elif message.video:
            name = message.video.file_name or suggest_name("video", "video/mp4")
            mime = message.video.mime_type or "video/mp4"
            size = message.video.file_size or 0
        elif message.audio:
            name = message.audio.file_name or suggest_name("audio", "audio/mpeg")
            mime = message.audio.mime_type or "audio/mpeg"
            size = message.audio.file_size or 0
        elif message.photo:
            name = suggest_name("photo", "image/jpeg")
            mime = "image/jpeg"
            size = message.photo[-1].file_size or 0
        else:
            name = "file"
            mime = "application/octet-stream"
            size = getattr(attachment, "file_size", 0) or 0

        name = safe_filename(name)
        category = get_category(mime)

        doc = mk_file(
            file_id=file_id,
            unique_id=unique_id,
            file_name=name,
            mime_type=mime,
            file_size=size,
            owner_id=owner_id,
            message_id=storage_msg_id or message.message_id,
            folder_id=folder_id,
            file_hash=file_hash,
            tags=tags or [],
            category=category,
            is_vault=is_vault,
            caption=message.caption,
            storage_channel_id=storage_channel_id or cfg.STORAGE_CHANNEL_ID,
        )

        result = await files().insert_one(doc)
        doc["_id"] = result.inserted_id

        await users().update_one(
            {"user_id": owner_id},
            {"$inc": {"storage_used": size, "file_count": 1}},
        )

        if folder_id:
            from database import folders
            await folders().update_one(
                {"_id": ObjectId(folder_id)},
                {"$inc": {"file_count": 1, "size": size}},
            )

        log.info("file saved: %s by user %d (%.1f MB)", name, owner_id, size / 1024 / 1024)
        return doc, False

    # ── read ──────────────────────────────────────────────────────────────────

    @staticmethod
    async def get_by_id(file_db_id: str) -> Optional[Dict[str, Any]]:
        cached = _file_cache.get(file_db_id)
        if cached is not None:
            return cached
        try:
            doc = await files().find_one({"_id": ObjectId(file_db_id), "is_deleted": False})
            if doc:
                _file_cache[file_db_id] = doc
            return doc
        except Exception:
            return None

    @staticmethod
    async def list_user_files(
        owner_id: int,
        folder_id: Optional[str] = None,
        category: Optional[str] = None,
        is_vault: bool = False,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
    ) -> Tuple[List[Dict[str, Any]], int]:
        query: Dict[str, Any] = {"owner_id": owner_id, "is_deleted": False, "is_vault": is_vault}
        if folder_id:
            query["folder_id"] = folder_id
        else:
            if not is_vault:
                query["folder_id"] = None
        if category:
            query["category"] = category

        total = await files().count_documents(query)
        sort_field = {"latest": "created_at", "size": "file_size", "popular": "downloads"}.get(sort_by, "created_at")
        projection = {
            "_id": 1,
            "file_name": 1,
            "file_size": 1,
            "category": 1,
            "created_at": 1,
            "downloads": 1,
            "folder_id": 1,
            "is_vault": 1
        }
        cursor = files().find(query, projection).sort(sort_field, -1).skip(skip).limit(limit)
        docs = await cursor.to_list(limit)
        return docs, total

    # ── update ────────────────────────────────────────────────────────────────

    @staticmethod
    async def rename(file_db_id: str, new_name: str, owner_id: int) -> bool:
        name = safe_filename(new_name)
        result = await files().update_one(
            {"_id": ObjectId(file_db_id), "owner_id": owner_id},
            {"$set": {"file_name": name, "updated_at": datetime.utcnow()}},
        )
        _file_cache.pop(file_db_id, None)
        return result.modified_count > 0

    @staticmethod
    async def move(file_db_id: str, target_folder_id: Optional[str], owner_id: int) -> bool:
        result = await files().update_one(
            {"_id": ObjectId(file_db_id), "owner_id": owner_id},
            {"$set": {"folder_id": target_folder_id, "updated_at": datetime.utcnow()}},
        )
        _file_cache.pop(file_db_id, None)
        return result.modified_count > 0

    @staticmethod
    async def add_tags(file_db_id: str, tag_list: List[str], owner_id: int) -> None:
        await files().update_one(
            {"_id": ObjectId(file_db_id), "owner_id": owner_id},
            {"$addToSet": {"tags": {"$each": tag_list}}, "$set": {"updated_at": datetime.utcnow()}},
        )
        _file_cache.pop(file_db_id, None)

    @staticmethod
    async def increment_downloads(file_db_id: str) -> None:
        await files().update_one(
            {"_id": ObjectId(file_db_id)},
            {"$inc": {"downloads": 1}},
        )
        _file_cache.pop(file_db_id, None)

    @staticmethod
    async def increment_views(file_db_id: str) -> None:
        await files().update_one(
            {"_id": ObjectId(file_db_id)},
            {"$inc": {"views": 1}},
        )
        _file_cache.pop(file_db_id, None)

    # ── delete ────────────────────────────────────────────────────────────────

    @staticmethod
    async def soft_delete(file_db_id: str, owner_id: int) -> Optional[Dict[str, Any]]:
        doc = await files().find_one({"_id": ObjectId(file_db_id), "owner_id": owner_id})
        if not doc:
            return None
        await files().update_one(
            {"_id": ObjectId(file_db_id)},
            {"$set": {"is_deleted": True, "updated_at": datetime.utcnow()}},
        )
        await users().update_one(
            {"user_id": owner_id},
            {"$inc": {"storage_used": -doc.get("file_size", 0), "file_count": -1}},
        )
        _file_cache.pop(file_db_id, None)
        return doc

    # ── stats ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def total_count() -> int:
        return await files().count_documents({"is_deleted": False})

    @staticmethod
    async def total_size() -> int:
        pipeline = [
            {"$match": {"is_deleted": False}},
            {"$group": {"_id": None, "total": {"$sum": "$file_size"}}},
        ]
        result = await files().aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0

    @staticmethod
    async def category_breakdown() -> Dict[str, int]:
        pipeline = [
            {"$match": {"is_deleted": False}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]
        result = await files().aggregate(pipeline).to_list(20)
        return {r["_id"]: r["count"] for r in result}
