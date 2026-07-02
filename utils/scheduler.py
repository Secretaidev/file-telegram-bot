"""
vault bot — async background scheduler
manages cleanup, backup, subscription expiry, vault auto-lock
"""

from __future__ import annotations
import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot
from config import cfg
from utils.logger import system_log

log = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="UTC")


async def _expire_subscriptions() -> None:
    from database import subscriptions, users
    now = datetime.utcnow()
    expired = await subscriptions().find({"expires_at": {"$lte": now}}).to_list(None)
    for sub in expired:
        await users().update_one(
            {"user_id": sub["user_id"]},
            {"$set": {"role": "user"}}
        )
        await subscriptions().delete_one({"_id": sub["_id"]})
    if expired:
        log.info("expired %d subscriptions", len(expired))


async def _expire_links() -> None:
    from database import links
    now = datetime.utcnow()
    result = await links().update_many(
        {"expires_at": {"$lte": now}, "is_active": True},
        {"$set": {"is_active": False}},
    )
    if result.modified_count:
        log.info("deactivated %d expired share links", result.modified_count)


async def _expire_vault_sessions() -> None:
    from database import sessions
    now = datetime.utcnow()
    await sessions().delete_many({"expires_at": {"$lte": now}})


async def _cleanup_deleted_files() -> None:
    from database import files
    cutoff = datetime.utcnow() - timedelta(days=30)
    result = await files().delete_many({"is_deleted": True, "updated_at": {"$lte": cutoff}})
    if result.deleted_count:
        log.info("hard deleted %d trashed files", result.deleted_count)


async def _cleanup_old_logs() -> None:
    """Delete MongoDB logs older than 7 days to keep server load low."""
    from database import logs
    cutoff = datetime.utcnow() - timedelta(days=7)
    result = await logs().delete_many({"created_at": {"$lte": cutoff}})
    if result.deleted_count:
        log.info("auto-deleted %d old server logs", result.deleted_count)


async def _auto_backup(bot: Bot) -> None:
    from services.backup_service import BackupService
    try:
        path = await BackupService.create_backup()
        # send to configured backup channels
        await BackupService.send_to_channels(bot, path)
        # keep only the 5 most recent local backup files
        deleted = await BackupService.cleanup_old_backups(keep=5)
        if deleted:
            log.info("cleaned up %d old local backup files", deleted)
        await system_log(bot, f"scheduled backup completed → {path}")
    except Exception as e:
        log.error("backup failed: %s", e)


def start(bot: Bot) -> None:
    _scheduler.add_job(_expire_subscriptions, IntervalTrigger(hours=1), id="expire_subs")
    _scheduler.add_job(_expire_links, IntervalTrigger(hours=1), id="expire_links")
    _scheduler.add_job(_expire_vault_sessions, IntervalTrigger(minutes=10), id="expire_vault")
    _scheduler.add_job(_cleanup_deleted_files, IntervalTrigger(hours=12), id="cleanup_files")
    _scheduler.add_job(_cleanup_old_logs, IntervalTrigger(hours=24), id="cleanup_logs")
    _scheduler.add_job(
        lambda: asyncio.ensure_future(_auto_backup(bot)),
        IntervalTrigger(hours=cfg.BACKUP_INTERVAL_HOURS),
        id="auto_backup",
    )
    _scheduler.start()
    log.info("scheduler started with %d jobs", len(_scheduler.get_jobs()))


def stop() -> None:
    _scheduler.shutdown(wait=False)
    log.info("scheduler stopped")
