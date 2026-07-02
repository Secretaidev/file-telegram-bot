"""
vault bot — share link service
cdn-style tokenised links with expiry, one-time access, password protection
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from bson import ObjectId
from database import links, link_doc as mk_link
from utils.helpers import generate_token, hash_pin

log = logging.getLogger(__name__)


class ShareService:

    @staticmethod
    async def create_link(
        file_db_id: str,
        owner_id: int,
        expiry_hours: int = 0,
        one_time: bool = False,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = generate_token(20)
        expires_at = None
        if expiry_hours > 0:
            expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)

        hashed_pw = hash_pin(password) if password else None
        doc = mk_link(
            token=token,
            file_id=file_db_id,
            owner_id=owner_id,
            expires_at=expires_at,
            one_time=one_time,
            password=hashed_pw,
        )
        result = await links().insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    @staticmethod
    async def resolve_token(token: str) -> Tuple[Optional[Dict[str, Any]], str]:
        doc = await links().find_one({"token": token, "is_active": True})
        if not doc:
            return None, "link not found or revoked"
        if doc.get("expires_at") and doc["expires_at"] < datetime.utcnow():
            await links().update_one({"_id": doc["_id"]}, {"$set": {"is_active": False}})
            return None, "link has expired"
        return doc, "ok"

    @staticmethod
    async def verify_password(link_doc: Dict[str, Any], password: str) -> bool:
        stored = link_doc.get("password")
        if not stored:
            return True
        return stored == hash_pin(password)

    @staticmethod
    async def record_access(link_db_id: str, downloaded: bool = False) -> None:
        update = {"$inc": {"views": 1}}
        if downloaded:
            update["$inc"]["downloads"] = 1
        await links().update_one({"_id": ObjectId(link_db_id)}, update)

    @staticmethod
    async def deactivate_if_one_time(link_doc: Dict[str, Any]) -> None:
        if link_doc.get("one_time"):
            await links().update_one(
                {"_id": link_doc["_id"]},
                {"$set": {"is_active": False}},
            )

    @staticmethod
    async def revoke(link_db_id: str, owner_id: int) -> bool:
        result = await links().update_one(
            {"_id": ObjectId(link_db_id), "owner_id": owner_id},
            {"$set": {"is_active": False}},
        )
        return result.modified_count > 0

    @staticmethod
    async def list_user_links(owner_id: int, page: int = 0, limit: int = 5) -> Tuple[list, int]:
        query = {"owner_id": owner_id, "is_active": True}
        total = await links().count_documents(query)
        cursor = links().find(query).sort("created_at", -1).skip(page * limit).limit(limit)
        return await cursor.to_list(limit), total
