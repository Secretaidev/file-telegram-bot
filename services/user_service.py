"""
vault bot — user service
all user-related db operations
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from database import users, files, subscriptions
from database.models import Role

log = logging.getLogger(__name__)


class UserService:

    @staticmethod
    async def get(user_id: int) -> Optional[Dict[str, Any]]:
        return await users().find_one({"user_id": user_id})

    @staticmethod
    async def update(user_id: int, data: Dict[str, Any]) -> None:
        await users().update_one({"user_id": user_id}, {"$set": data})

    @staticmethod
    async def is_premium(user_id: int) -> bool:
        doc = await users().find_one({"user_id": user_id}, {"role": 1})
        if not doc:
            return False
        return doc.get("role") in (Role.PREMIUM.value, Role.ADMIN.value, Role.OWNER.value)

    @staticmethod
    async def get_role(user_id: int) -> str:
        doc = await users().find_one({"user_id": user_id}, {"role": 1})
        return doc.get("role", Role.USER.value) if doc else Role.USER.value

    @staticmethod
    async def ban(user_id: int) -> None:
        await users().update_one({"user_id": user_id}, {"$set": {"is_banned": True}})

    @staticmethod
    async def unban(user_id: int) -> None:
        await users().update_one({"user_id": user_id}, {"$set": {"is_banned": False}})

    @staticmethod
    async def get_storage_used(user_id: int) -> int:
        doc = await users().find_one({"user_id": user_id}, {"storage_used": 1})
        return doc.get("storage_used", 0) if doc else 0

    @staticmethod
    async def add_to_recent(user_id: int, file_db_id: str) -> None:
        fid = str(file_db_id)
        await users().update_one(
            {"user_id": user_id},
            {"$pull": {"recent": fid}},
        )
        await users().update_one(
            {"user_id": user_id},
            {"$push": {"recent": {"$each": [fid], "$slice": -20}}},
        )

    @staticmethod
    async def toggle_favorite(user_id: int, file_db_id: str) -> bool:
        fid = str(file_db_id)
        doc = await users().find_one({"user_id": user_id}, {"favorites": 1})
        favs = doc.get("favorites", []) if doc else []
        if fid in favs:
            await users().update_one({"user_id": user_id}, {"$pull": {"favorites": fid}})
            return False
        else:
            await users().update_one({"user_id": user_id}, {"$addToSet": {"favorites": fid}})
            return True

    @staticmethod
    async def get_favorites(user_id: int) -> List[str]:
        doc = await users().find_one({"user_id": user_id}, {"favorites": 1})
        return doc.get("favorites", []) if doc else []

    @staticmethod
    async def get_recent(user_id: int) -> List[str]:
        doc = await users().find_one({"user_id": user_id}, {"recent": 1})
        ids = doc.get("recent", []) if doc else []
        return list(reversed(ids))

    @staticmethod
    async def count_all() -> int:
        return await users().count_documents({})

    @staticmethod
    async def count_premium() -> int:
        return await users().count_documents({"role": {"$in": ["premium", "admin", "owner"]}})

    @staticmethod
    async def count_banned() -> int:
        return await users().count_documents({"is_banned": True})

    @staticmethod
    async def list_users(skip: int = 0, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = users().find({}).sort("joined_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(limit)

    @staticmethod
    async def search_user(query: str) -> Optional[Dict[str, Any]]:
        try:
            uid = int(query)
            doc = await users().find_one({"user_id": uid})
            if doc:
                return doc
        except ValueError:
            pass
        return await users().find_one({"username": query.lstrip("@")})
