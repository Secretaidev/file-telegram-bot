"""
sᴇᴄʀᴇᴛ ғɪʟᴇ sᴛᴏʀɪɴɢ ʙᴏᴛ — subscription service
premium plan management, payment tracking, approval workflow
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId
from database import subscriptions, payments, users
from database.models import subscription_doc as mk_sub, payment_doc as mk_payment, PaymentStatus, Role

log = logging.getLogger(__name__)

PLANS = {
    "monthly":  {"label": "monthly",  "days": 30, "amount": 10},
}


class SubscriptionService:

    @staticmethod
    async def get_active(user_id: int) -> Optional[Dict[str, Any]]:
        return await subscriptions().find_one(
            {"user_id": user_id, "expires_at": {"$gt": datetime.utcnow()}},
        )

    @staticmethod
    async def grant(user_id: int, plan: str, granted_by: int) -> Dict[str, Any]:
        plan_data = PLANS.get(plan, PLANS["monthly"])
        expires_at = datetime.utcnow() + timedelta(days=plan_data["days"])

        doc = mk_sub(user_id=user_id, plan=plan, expires_at=expires_at, granted_by=granted_by)
        await subscriptions().replace_one({"user_id": user_id}, doc, upsert=True)

        await users().update_one(
            {"user_id": user_id},
            {"$set": {"role": Role.PREMIUM.value}},
        )
        from middlewares.auth import invalidate_user_cache
        invalidate_user_cache(user_id)
        log.info("premium granted: user=%d plan=%s expires=%s", user_id, plan, expires_at)
        return doc

    @staticmethod
    async def revoke(user_id: int) -> None:
        await subscriptions().delete_one({"user_id": user_id})
        await users().update_one(
            {"user_id": user_id},
            {"$set": {"role": Role.USER.value}},
        )
        from middlewares.auth import invalidate_user_cache
        invalidate_user_cache(user_id)

    # ── payment workflow ──────────────────────────────────────────────────────

    @staticmethod
    async def create_payment(
        user_id: int,
        plan: str,
        screenshot_file_id: str,
        screenshot_message_id: int,
    ) -> Dict[str, Any]:
        plan_data = PLANS.get(plan, PLANS["monthly"])
        doc = mk_payment(
            user_id=user_id,
            plan=plan,
            amount=plan_data["amount"],
            screenshot_file_id=screenshot_file_id,
            screenshot_message_id=screenshot_message_id,
        )
        result = await payments().insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    @staticmethod
    async def get_payment(payment_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await payments().find_one({"_id": ObjectId(payment_id)})
        except Exception:
            return None

    @staticmethod
    async def list_pending() -> List[Dict[str, Any]]:
        cursor = payments().find({"status": PaymentStatus.PENDING.value}).sort("created_at", -1)
        return await cursor.to_list(50)

    @staticmethod
    async def approve_payment(payment_id: str, admin_id: int) -> Optional[Dict[str, Any]]:
        doc = await SubscriptionService.get_payment(payment_id)
        if not doc or doc["status"] != PaymentStatus.PENDING.value:
            return None
        await payments().update_one(
            {"_id": ObjectId(payment_id)},
            {"$set": {
                "status":      PaymentStatus.APPROVED.value,
                "reviewed_by": admin_id,
                "reviewed_at": datetime.utcnow(),
            }},
        )
        await SubscriptionService.grant(doc["user_id"], doc["plan"], admin_id)
        return doc

    @staticmethod
    async def reject_payment(payment_id: str, admin_id: int) -> Optional[Dict[str, Any]]:
        doc = await SubscriptionService.get_payment(payment_id)
        if not doc or doc["status"] != PaymentStatus.PENDING.value:
            return None
        await payments().update_one(
            {"_id": ObjectId(payment_id)},
            {"$set": {
                "status":      PaymentStatus.REJECTED.value,
                "reviewed_by": admin_id,
                "reviewed_at": datetime.utcnow(),
            }},
        )
        return doc

    @staticmethod
    async def count_payments_by_status() -> Dict[str, int]:
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        result = await payments().aggregate(pipeline).to_list(10)
        return {r["_id"]: r["count"] for r in result}
