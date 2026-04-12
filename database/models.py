"""
vault bot — database document schemas
typed dicts used as schema reference and for constructing documents
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class Role(str, Enum):
    USER    = "user"
    PREMIUM = "premium"
    ADMIN   = "admin"
    OWNER   = "owner"
    BANNED  = "banned"


class PaymentStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FileCategory(str, Enum):
    DOCUMENT = "document"
    VIDEO    = "video"
    AUDIO    = "audio"
    PHOTO    = "photo"
    ARCHIVE  = "archive"
    OTHER    = "other"


def user_doc(
    user_id: int,
    username: Optional[str],
    full_name: str,
    role: Role = Role.USER,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "user_id":        user_id,
        "username":       username,
        "full_name":      full_name,
        "role":           role.value,
        "is_banned":      False,
        "storage_used":   0,
        "file_count":     0,
        "favorites":      [],
        "recent":         [],
        "joined_at":      now,
        "last_seen":      now,
    }


def file_doc(
    file_id: str,
    unique_id: str,
    file_name: str,
    mime_type: str,
    file_size: int,
    owner_id: int,
    message_id: int,
    folder_id: Optional[str] = None,
    file_hash: Optional[str] = None,
    tags: Optional[List[str]] = None,
    category: FileCategory = FileCategory.OTHER,
    is_vault: bool = False,
    caption: Optional[str] = None,
    storage_channel_id: int = 0,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "file_id":            file_id,
        "unique_id":          unique_id,
        "file_name":          file_name,
        "mime_type":          mime_type,
        "file_size":          file_size,
        "owner_id":           owner_id,
        "message_id":         message_id,
        "storage_channel_id": storage_channel_id,
        "folder_id":          folder_id,
        "file_hash":          file_hash,
        "tags":               tags or [],
        "category":           category.value,
        "is_vault":           is_vault,
        "is_deleted":         False,
        "caption":            caption,
        "downloads":          0,
        "views":              0,
        "is_favorite":        False,
        "versions":           [],
        "created_at":         now,
        "updated_at":         now,
    }


def folder_doc(
    name: str,
    owner_id: int,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "name":       name,
        "owner_id":   owner_id,
        "parent_id":  parent_id,
        "file_count": 0,
        "size":       0,
        "created_at": now,
        "updated_at": now,
    }


def link_doc(
    token: str,
    file_id: str,
    owner_id: int,
    expires_at: Optional[datetime] = None,
    one_time: bool = False,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "token":      token,
        "file_id":    file_id,
        "owner_id":   owner_id,
        "expires_at": expires_at,
        "one_time":   one_time,
        "password":   password,
        "views":      0,
        "downloads":  0,
        "is_active":  True,
        "created_at": now,
    }


def payment_doc(
    user_id: int,
    plan: str,
    amount: float,
    screenshot_file_id: str,
    screenshot_message_id: int,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "user_id":                user_id,
        "plan":                   plan,
        "amount":                 amount,
        "screenshot_file_id":     screenshot_file_id,
        "screenshot_message_id":  screenshot_message_id,
        "status":                 PaymentStatus.PENDING.value,
        "reviewed_by":            None,
        "reviewed_at":            None,
        "created_at":             now,
    }


def subscription_doc(
    user_id: int,
    plan: str,
    expires_at: datetime,
    granted_by: int,
) -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "user_id":    user_id,
        "plan":       plan,
        "expires_at": expires_at,
        "granted_by": granted_by,
        "created_at": now,
        "updated_at": now,
    }


def log_doc(
    user_id: int,
    action: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "user_id":    user_id,
        "action":     action,
        "details":    details or {},
        "created_at": datetime.utcnow(),
    }


def vault_session_doc(
    user_id: int,
    expires_at: datetime,
) -> Dict[str, Any]:
    return {
        "user_id":    user_id,
        "expires_at": expires_at,
        "created_at": datetime.utcnow(),
    }
