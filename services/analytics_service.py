"""
vault bot — analytics service
lightweight per-user daily usage tracking
"""

from __future__ import annotations
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from database import analytics

log = logging.getLogger(__name__)


class AnalyticsService:

    @staticmethod
    async def record(user_id: int, action: str, meta: Optional[Dict[str, Any]] = None) -> None:
        today = date.today().isoformat()
        try:
            await analytics().update_one(
                {"user_id": user_id, "date": today},
                {
                    "$inc": {f"actions.{action}": 1},
                    "$set": {"updated_at": datetime.utcnow()},
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                },
                upsert=True,
            )
        except Exception as e:
            log.warning("analytics record failed: %s", e)

    @staticmethod
    async def get_user_summary(user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        from datetime import timedelta
        since = (date.today() - timedelta(days=days)).isoformat()
        cursor = analytics().find(
            {"user_id": user_id, "date": {"$gte": since}},
        ).sort("date", 1)
        return await cursor.to_list(days)

    @staticmethod
    async def global_actions_today() -> Dict[str, int]:
        today = date.today().isoformat()
        pipeline = [
            {"$match": {"date": today}},
            {"$project": {"actions": 1}},
            {"$group": {
                "_id": None,
                "uploads":   {"$sum": "$actions.upload"},
                "downloads": {"$sum": "$actions.download"},
                "searches":  {"$sum": "$actions.search"},
            }},
        ]
        result = await analytics().aggregate(pipeline).to_list(1)
        if not result:
            return {"uploads": 0, "downloads": 0, "searches": 0}
        r = result[0]
        return {
            "uploads":   r.get("uploads", 0) or 0,
            "downloads": r.get("downloads", 0) or 0,
            "searches":  r.get("searches", 0) or 0,
        }
