"""
vault bot — search service
full-text search, filters, sorting, pagination via mongodb text index
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
from database import files
from config import cfg

log = logging.getLogger(__name__)


class SearchService:

    @staticmethod
    async def search(
        query: str,
        owner_id: int,
        category: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "latest",
        page: int = 0,
        include_vault: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:

        match: Dict[str, Any] = {
            "owner_id": owner_id,
            "is_deleted": False,
        }

        if not include_vault:
            match["is_vault"] = False

        if query.strip():
            match["$text"] = {"$search": query}

        if category:
            match["category"] = category

        size_filter: Dict[str, int] = {}
        if min_size is not None:
            size_filter["$gte"] = min_size
        if max_size is not None:
            size_filter["$lte"] = max_size
        if size_filter:
            match["file_size"] = size_filter

        if tags:
            match["tags"] = {"$all": tags}

        sort_map = {
            "latest":  [("created_at", -1)],
            "size":    [("file_size", -1)],
            "popular": [("downloads", -1)],
            "name":    [("file_name", 1)],
        }
        if query.strip():
            sort_map["relevance"] = [("score", {"$meta": "textScore"})]

        sort = sort_map.get(sort_by, sort_map["latest"])

        skip = page * cfg.SEARCH_PAGE_SIZE
        limit = cfg.SEARCH_PAGE_SIZE

        total = await files().count_documents(match)

        pipeline = [
            {"$match": match},
            *(
                [{"$addFields": {"score": {"$meta": "textScore"}}}]
                if query.strip() and sort_by == "relevance" else []
            ),
            {"$sort": dict(sort)},
            {"$skip": skip},
            {"$limit": limit},
        ]

        results = await files().aggregate(pipeline).to_list(limit)
        return results, total

    @staticmethod
    async def suggest_tags(partial: str, owner_id: int, limit: int = 5) -> List[str]:
        pipeline = [
            {"$match": {"owner_id": owner_id, "is_deleted": False}},
            {"$unwind": "$tags"},
            {"$match": {"tags": {"$regex": f"^{partial}", "$options": "i"}}},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        result = await files().aggregate(pipeline).to_list(limit)
        return [r["_id"] for r in result]

    @staticmethod
    async def get_popular_tags(owner_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        pipeline = [
            {"$match": {"owner_id": owner_id, "is_deleted": False}},
            {"$unwind": "$tags"},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
        return await files().aggregate(pipeline).to_list(limit)
