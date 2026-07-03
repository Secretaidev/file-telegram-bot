"""
vault bot — database connection layer
motor async mongodb driver with lazy init
"""

from __future__ import annotations
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import cfg

log = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect() -> None:
    global _client, _db
    import asyncio
    retries = 3
    delay = 2
    for attempt in range(retries):
        try:
            _client = AsyncIOMotorClient(cfg.MONGO_URI, serverSelectionTimeoutMS=5000)
            _db = _client[cfg.DB_NAME]
            await _db.command("ping")
            log.info("mongodb connected — database: %s", cfg.DB_NAME)
            await _create_indexes()
            return
        except Exception as e:
            log.error("mongodb connection attempt %d/%d failed: %s", attempt + 1, retries, e)
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)
            delay *= 2


async def disconnect() -> None:
    global _client
    if _client:
        _client.close()
        log.info("mongodb disconnected")


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("database not initialised — call connect() first")
    return _db


# — collection accessors
def users():        return get_db()["users"]
def files():        return get_db()["files"]
def folders():      return get_db()["folders"]
def vault():        return get_db()["vault"]
def logs():         return get_db()["logs"]
def sessions():     return get_db()["sessions"]
def links():        return get_db()["links"]
def payments():     return get_db()["payments"]
def subscriptions():return get_db()["subscriptions"]
def tags():         return get_db()["tags"]
def analytics():    return get_db()["analytics"]
def clones():       return get_db()["clones"]


async def _create_indexes() -> None:
    db = get_db()

    await db["users"].create_index("user_id", unique=True)
    await db["users"].create_index("username")
    await db["users"].create_index("role")
    await db["users"].create_index("joined_at")

    await db["files"].create_index("file_hash")
    await db["files"].create_index("owner_id")
    await db["files"].create_index("folder_id")
    await db["files"].create_index("mime_type")
    await db["files"].create_index("tags")
    await db["files"].create_index("is_vault")
    await db["files"].create_index("is_deleted")
    await db["files"].create_index("created_at")
    await db["files"].create_index([("file_name", "text"), ("tags", "text")])
    # Compound index for listing user files (the most common query)
    await db["files"].create_index([("owner_id", 1), ("is_deleted", 1), ("is_vault", 1), ("created_at", -1)])

    await db["folders"].create_index([("owner_id", 1), ("parent_id", 1)])
    await db["folders"].create_index("owner_id")

    await db["links"].create_index("token", unique=True)
    await db["links"].create_index("file_id")
    # TTL Index: Automatically deletes document when current time > expires_at
    await db["links"].create_index("expires_at", expireAfterSeconds=0)

    await db["sessions"].create_index("user_id", unique=True)
    await db["sessions"].create_index("expires_at", expireAfterSeconds=0)

    await db["payments"].create_index("user_id")
    await db["payments"].create_index("status")
    await db["payments"].create_index("created_at")

    await db["subscriptions"].create_index("user_id", unique=True)
    await db["subscriptions"].create_index("expires_at", expireAfterSeconds=0)

    await db["logs"].create_index("user_id")
    await db["logs"].create_index("action")
    await db["logs"].create_index("created_at")

    await db["analytics"].create_index([("user_id", 1), ("date", 1)])
    await db["clones"].create_index("token", unique=True)
    await db["clones"].create_index("bot_id", unique=True)
    await db["clones"].create_index("owner_id")

    log.info("mongodb indexes created")
