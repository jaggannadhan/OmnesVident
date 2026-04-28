"""
api_users.py — Public-API user accounts and key issuance.

A simple Firestore-backed user store for the v1 public REST API.

Collection: api_users
  doc_id            = SHA-256(api_key)            # also serves as a fast lookup index
  fields:
    user_id          : str  (uuid4)
    name             : str
    email            : str   (unique, lowercased)
    access_level     : "super-user" | "community"
    api_key_prefix   : str   (first 12 chars of the raw key, for display only)
    api_key_hash     : str   (sha256 hex of the raw key)
    created_at       : datetime (utc)
    revoked          : bool
    rate_limit_per_min : int  (None = use global default; 0 = unlimited)

We never store the raw key. The user sees it exactly once at signup time.

In-memory cache:
    _CACHE: dict[key_hash, user_record]
  populated on first successful lookup; survives the lifetime of the process.
  Cloud Run instances scale horizontally — each instance has its own cache,
  which is fine since auth is read-mostly and Firestore reads are cheap.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "")
_USERS_COLLECTION  = "api_users"

# Process-local cache: key_hash -> user dict
_CACHE: Dict[str, Dict[str, Any]] = {}


# ─── Key generation & hashing ────────────────────────────────────────────────

def generate_api_key() -> str:
    """Return a fresh API key in the form 'ov_<48 hex chars>'."""
    return f"ov_{secrets.token_hex(24)}"


def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ─── Firestore client (lazy singleton) ───────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not _FIRESTORE_PROJECT:
        return None
    try:
        from google.cloud import firestore  # type: ignore
        _client = firestore.AsyncClient(project=_FIRESTORE_PROJECT)
        logger.info("api_users: Firestore connected (project=%s).", _FIRESTORE_PROJECT)
    except Exception as exc:
        logger.warning("api_users: Firestore unavailable — %s", exc)
        _client = None
    return _client


# ─── User CRUD ───────────────────────────────────────────────────────────────

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Return the first user record matching `email` (case-insensitive), or None."""
    client = _get_client()
    if client is None:
        return None
    try:
        snap = (
            client.collection(_USERS_COLLECTION)
            .where("email", "==", email.lower().strip())
            .limit(1)
            .stream()
        )
        async for doc in snap:
            return doc.to_dict()
    except Exception as exc:
        logger.error("get_user_by_email failed: %s", exc)
    return None


async def get_user_by_key_hash(key_hash: str) -> Optional[Dict[str, Any]]:
    """Cache-first lookup of a user by their api_key_hash."""
    if key_hash in _CACHE:
        return _CACHE[key_hash]

    client = _get_client()
    if client is None:
        return None
    try:
        doc_ref = client.collection(_USERS_COLLECTION).document(key_hash)
        snap = await doc_ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            if not data.get("revoked"):
                _CACHE[key_hash] = data
                return data
    except Exception as exc:
        logger.error("get_user_by_key_hash failed: %s", exc)
    return None


async def create_user(
    *,
    name: str,
    email: str,
    access_level: str = "community",
    rate_limit_per_min: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a user with a freshly minted API key.

    Returns: { user_id, name, email, access_level, api_key (raw — only time
              we ever return this), api_key_prefix, created_at }
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Firestore is not configured; cannot create user.")

    email = email.lower().strip()
    existing = await get_user_by_email(email)
    if existing:
        raise ValueError(f"A user with email '{email}' already exists.")

    raw_key   = generate_api_key()
    key_hash  = hash_api_key(raw_key)
    user_id   = str(uuid.uuid4())
    now       = datetime.now(tz=timezone.utc)

    record: Dict[str, Any] = {
        "user_id":            user_id,
        "name":               name.strip(),
        "email":              email,
        "access_level":       access_level,
        "api_key_prefix":     raw_key[:12],
        "api_key_hash":       key_hash,
        "created_at":         now,
        "revoked":            False,
        "rate_limit_per_min": rate_limit_per_min,
    }

    await client.collection(_USERS_COLLECTION).document(key_hash).set(record)
    _CACHE[key_hash] = record
    logger.info("api_users: created %s (level=%s) — key prefix=%s",
                email, access_level, raw_key[:12])

    return {**record, "api_key": raw_key}


async def upgrade_to_super_user(email: str) -> bool:
    """Idempotent — promote an existing user to access_level='super-user'."""
    client = _get_client()
    if client is None:
        return False
    user = await get_user_by_email(email)
    if not user:
        return False
    key_hash = user["api_key_hash"]
    await client.collection(_USERS_COLLECTION).document(key_hash).update({
        "access_level": "super-user",
        "rate_limit_per_min": 0,
    })
    _CACHE.pop(key_hash, None)  # invalidate cached copy
    return True


def invalidate_cache(key_hash: Optional[str] = None) -> None:
    """Clear the per-process auth cache (single key or all)."""
    if key_hash:
        _CACHE.pop(key_hash, None)
    else:
        _CACHE.clear()
