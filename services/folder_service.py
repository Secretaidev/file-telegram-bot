"""
vault bot — folder service
hierarchical folder tree: create, navigate, rename, delete
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from database import folders, files
from database.models import folder_doc as mk_folder
from cachetools import TTLCache
from config import cfg

log = logging.getLogger(__name__)

# Bounded cache to optimize hierarchical folder tree lookups and recursive breadcrumb loads
_folder_cache: TTLCache[str, Dict[str, Any]] = TTLCache(maxsize=1000, ttl=300)


class FolderService:

    @staticmethod
    async def create(name: str, owner_id: int, parent_id: Optional[str] = None) -> Dict[str, Any]:
        doc = mk_folder(name=name, owner_id=owner_id, parent_id=parent_id)
        result = await folders().insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    @staticmethod
    async def get_by_id(folder_id: str) -> Optional[Dict[str, Any]]:
        cached = _folder_cache.get(folder_id)
        if cached is not None:
            return cached
        try:
            doc = await folders().find_one({"_id": ObjectId(folder_id)})
            if doc:
                _folder_cache[folder_id] = doc
            return doc
        except Exception:
            return None

    @staticmethod
    async def list_children(owner_id: int, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"owner_id": owner_id, "parent_id": parent_id}
        cursor = folders().find(query).sort("name", 1)
        return await cursor.to_list(100)

    @staticmethod
    async def list_files_in(
        owner_id: int,
        folder_id: Optional[str],
        page: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query: Dict[str, Any] = {
            "owner_id": owner_id,
            "folder_id": folder_id,
            "is_deleted": False,
            "is_vault": False,
        }
        skip = page * cfg.PAGE_SIZE
        total = await files().count_documents(query)
        cursor = files().find(query).sort("created_at", -1).skip(skip).limit(cfg.PAGE_SIZE)
        return await cursor.to_list(cfg.PAGE_SIZE), total

    @staticmethod
    async def rename(folder_id: str, new_name: str, owner_id: int) -> bool:
        result = await folders().update_one(
            {"_id": ObjectId(folder_id), "owner_id": owner_id},
            {"$set": {"name": new_name, "updated_at": datetime.utcnow()}},
        )
        _folder_cache.pop(folder_id, None)
        return result.modified_count > 0

    @staticmethod
    async def delete(folder_id: str, owner_id: int) -> bool:
        children = await FolderService.list_children(owner_id, folder_id)
        for child in children:
            await FolderService.delete(str(child["_id"]), owner_id)
        await files().update_many(
            {"folder_id": folder_id, "owner_id": owner_id},
            {"$set": {"folder_id": None, "updated_at": datetime.utcnow()}},
        )
        result = await folders().delete_one({"_id": ObjectId(folder_id), "owner_id": owner_id})
        _folder_cache.pop(folder_id, None)
        return result.deleted_count > 0

    @staticmethod
    async def breadcrumb(folder_id: Optional[str]) -> List[Dict[str, Any]]:
        trail = []
        current = folder_id
        while current:
            doc = await FolderService.get_by_id(current)
            if not doc:
                break
            trail.insert(0, doc)
            current = doc.get("parent_id")
        return trail

    @staticmethod
    async def get_tree(owner_id: int, parent_id: Optional[str] = None, depth: int = 0) -> List[Dict[str, Any]]:
        if depth > 5:
            return []
        children = await FolderService.list_children(owner_id, parent_id)
        tree = []
        for child in children:
            node = dict(child)
            node["children"] = await FolderService.get_tree(owner_id, str(child["_id"]), depth + 1)
            tree.append(node)
        return tree
