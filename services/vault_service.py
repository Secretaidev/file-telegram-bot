"""
vault bot — vault service
pin-protected encrypted file vault with session management
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId
from database import sessions, users, vault_session_doc
from database import files
from utils.helpers import hash_pin
from utils.encryption import encrypt, decrypt
from config import cfg

log = logging.getLogger(__name__)


class VaultService:

    # ── pin management ────────────────────────────────────────────────────────

    @staticmethod
    async def has_pin(user_id: int) -> bool:
        doc = await users().find_one({"user_id": user_id}, {"vault_pin": 1})
        return bool(doc and doc.get("vault_pin"))

    @staticmethod
    async def set_pin(user_id: int, pin: str) -> None:
        hashed = hash_pin(pin)
        await users().update_one(
            {"user_id": user_id},
            {"$set": {"vault_pin": hashed}},
        )

    @staticmethod
    async def verify_pin(user_id: int, pin: str) -> bool:
        doc = await users().find_one({"user_id": user_id}, {"vault_pin": 1})
        if not doc or not doc.get("vault_pin"):
            return False
        return doc["vault_pin"] == hash_pin(pin)

    # ── session management ────────────────────────────────────────────────────

    @staticmethod
    async def create_session(user_id: int) -> None:
        expires = datetime.utcnow() + timedelta(seconds=cfg.SESSION_TIMEOUT)
        await sessions().replace_one(
            {"user_id": user_id},
            vault_session_doc(user_id, expires),
            upsert=True,
        )

    @staticmethod
    async def is_unlocked(user_id: int) -> bool:
        doc = await sessions().find_one({"user_id": user_id})
        if not doc:
            return False
        if doc["expires_at"] < datetime.utcnow():
            await sessions().delete_one({"user_id": user_id})
            return False
        await sessions().update_one(
            {"user_id": user_id},
            {"$set": {"expires_at": datetime.utcnow() + timedelta(seconds=cfg.SESSION_TIMEOUT)}},
        )
        return True

    @staticmethod
    async def lock(user_id: int) -> None:
        await sessions().delete_one({"user_id": user_id})

    # ── vault file operations ─────────────────────────────────────────────────

    @staticmethod
    async def list_vault_files(user_id: int, page: int = 0) -> tuple:
        query = {"owner_id": user_id, "is_vault": True, "is_deleted": False}
        skip = page * cfg.PAGE_SIZE
        total = await files().count_documents(query)
        cursor = files().find(query).sort("created_at", -1).skip(skip).limit(cfg.PAGE_SIZE)
        docs = await cursor.to_list(cfg.PAGE_SIZE)
        return docs, total

    @staticmethod
    async def move_to_vault(file_db_id: str, user_id: int) -> bool:
        result = await files().update_one(
            {"_id": ObjectId(file_db_id), "owner_id": user_id, "is_deleted": False},
            {"$set": {"is_vault": True, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count > 0

    @staticmethod
    async def move_from_vault(file_db_id: str, user_id: int) -> bool:
        result = await files().update_one(
            {"_id": ObjectId(file_db_id), "owner_id": user_id, "is_deleted": False},
            {"$set": {"is_vault": False, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count > 0
