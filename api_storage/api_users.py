"""
api_users.py — Public-API user accounts and key issuance.

A simple Firestore-backed user store for the v1 public REST API.

Collection: api_users
  doc_id            = SHA-256(api_key)            # also serves as a fast lookup index
  fields:
    user_id          : str  (uuid4)
    name             : str
    email            : str   (unique, lowercased)
    access_levels    : List[str]  (any subset of {basic, super_user, admin, premium})
    api_key_prefix   : str   (first 12 chars of the raw key, for display only)
    api_key_hash     : str   (sha256 hex of the raw key)
    password_hash    : str | None   (bcrypt; None means key-only auth)
    created_at       : datetime (utc)
    revoked          : bool
    rate_limit_per_min : int  (None = use tier default; 0 = unlimited)

Access-level rules:
  * exactly ONE level is required, OR
  * multiple levels are permitted only if `admin` is one of them.
  Examples — valid: ["basic"], ["premium"], ["admin", "super_user"];
            invalid: ["basic", "premium"], ["super_user", "premium"] (no admin).

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
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT", "")
_USERS_COLLECTION  = "api_users"

# Process-local cache: key_hash -> user dict
_CACHE: Dict[str, Dict[str, Any]] = {}


# ─── Access-level model ──────────────────────────────────────────────────────

VALID_ACCESS_LEVELS: List[str] = ["basic", "super_user", "admin", "premium"]
DEFAULT_ACCESS_LEVELS: List[str] = ["basic"]
# Any of these levels grants unlimited rate-limit:
UNLIMITED_LEVELS: set[str] = {"super_user", "admin"}


def normalize_levels(levels: Iterable[str]) -> List[str]:
    """Lowercase + dedupe + preserve order. Does NOT validate."""
    seen: set[str] = set()
    out: List[str] = []
    for raw in levels:
        if not raw:
            continue
        lvl = str(raw).strip().lower()
        if lvl and lvl not in seen:
            seen.add(lvl)
            out.append(lvl)
    return out


def validate_access_levels(levels: List[str]) -> None:
    """
    Enforce the access-level rules. Raises ValueError on violation.

    * each level must be one of VALID_ACCESS_LEVELS
    * exactly 1 level → always OK
    * 2+ levels      → "admin" must be present
    """
    if not levels:
        raise ValueError("access_levels must contain at least one level.")
    bad = [lvl for lvl in levels if lvl not in VALID_ACCESS_LEVELS]
    if bad:
        raise ValueError(
            f"Unknown access level(s): {bad}. "
            f"Valid options: {VALID_ACCESS_LEVELS}"
        )
    if len(levels) > 1 and "admin" not in levels:
        raise ValueError(
            "Multiple access levels are only permitted when 'admin' is one of them."
        )


def has_unlimited_access(levels: Iterable[str]) -> bool:
    """True if any level grants unlimited rate-limit (super_user or admin)."""
    return any(lvl in UNLIMITED_LEVELS for lvl in levels)


# ─── Backward-compat read shim ───────────────────────────────────────────────
# Older Firestore docs may still carry the legacy single-string `access_level`
# field with values "super-user" or "community". Translate on read so the rest
# of the code only ever sees the new `access_levels` list.

_LEGACY_LEVEL_MAP = {
    "super-user": ["super_user"],
    "super_user": ["super_user"],
    "community":  ["basic"],
    "basic":      ["basic"],
    "admin":      ["admin"],
    "premium":    ["premium"],
}


def _coerce_user(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mutate `record` in-place to ensure it has an `access_levels` list.
    Drop the legacy `access_level` string field once translated.
    """
    if "access_levels" in record and isinstance(record["access_levels"], list):
        record["access_levels"] = normalize_levels(record["access_levels"])
        return record
    legacy = record.pop("access_level", None)
    if isinstance(legacy, str):
        record["access_levels"] = _LEGACY_LEVEL_MAP.get(legacy.lower(), ["basic"])
    else:
        record["access_levels"] = list(DEFAULT_ACCESS_LEVELS)
    return record


# ─── Key generation & hashing ────────────────────────────────────────────────

def generate_api_key() -> str:
    """Return a fresh API key in the form 'ov_<48 hex chars>'."""
    return f"ov_{secrets.token_hex(24)}"


def hash_api_key(raw_key: str) -> str:
    """Return SHA-256 hex digest of the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ─── Password hashing (bcrypt) ───────────────────────────────────────────────
# bcrypt is the industry standard for password storage:
#   * incorporates a per-password salt,
#   * intentionally slow (cost factor) to defeat brute-force,
#   * upgrade path via cost-factor bumps.
# We never store raw passwords. Login compares the supplied password against
# the stored hash with bcrypt.checkpw.

_BCRYPT_ROUNDS = 12   # ~250ms per check on modern hardware; safe & fast enough

def hash_password(plain: str) -> str:
    import bcrypt  # type: ignore
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        import bcrypt  # type: ignore
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as exc:
        logger.warning("verify_password: bcrypt check failed — %s", exc)
        return False


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
            return _coerce_user(doc.to_dict() or {})
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
            data = _coerce_user(snap.to_dict() or {})
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
    password: Optional[str] = None,
    access_levels: Optional[List[str]] = None,
    rate_limit_per_min: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a user with a freshly minted API key.

    `password` is hashed with bcrypt before storage (we never persist the raw
    value).  When omitted (e.g. legacy admin scripts), the user can still
    authenticate via x-api-key but cannot login via /v1/auth/login.

    Returns: { user_id, name, email, access_levels, api_key (raw — only time
              we ever return this), api_key_prefix, created_at, ... }
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("Firestore is not configured; cannot create user.")

    levels = normalize_levels(access_levels or DEFAULT_ACCESS_LEVELS)
    validate_access_levels(levels)

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
        "access_levels":      levels,
        "api_key_prefix":     raw_key[:12],
        "api_key_hash":       key_hash,
        "password_hash":      hash_password(password) if password else None,
        "created_at":         now,
        "revoked":            False,
        "rate_limit_per_min": rate_limit_per_min,
    }

    await client.collection(_USERS_COLLECTION).document(key_hash).set(record)
    _CACHE[key_hash] = record
    logger.info("api_users: created %s (levels=%s, password=%s) — key prefix=%s",
                email, levels, "set" if password else "none", raw_key[:12])

    return {**record, "api_key": raw_key}


async def set_access_levels(email: str, levels: List[str]) -> bool:
    """
    Replace an existing user's access_levels list. Validates the new list
    against the same rules `create_user` enforces (admin must be present
    when assigning multiple levels).
    """
    levels = normalize_levels(levels)
    validate_access_levels(levels)

    client = _get_client()
    if client is None:
        return False
    user = await get_user_by_email(email)
    if not user:
        return False

    key_hash = user["api_key_hash"]
    update: Dict[str, Any] = {"access_levels": levels}
    # Drop any legacy single-string field from the document
    update["access_level"] = None    # Firestore will write null; will be ignored on read
    # If they're being granted unlimited tier, clear any custom rate limit so
    # the auth path uses the level-based default.
    if has_unlimited_access(levels):
        update["rate_limit_per_min"] = 0

    await client.collection(_USERS_COLLECTION).document(key_hash).update(update)
    _CACHE.pop(key_hash, None)
    logger.info("api_users: set %s access_levels=%s", email, levels)
    return True


async def set_password(email: str, password: str) -> bool:
    """Set or rotate the bcrypt password_hash for an existing user."""
    client = _get_client()
    if client is None:
        return False
    user = await get_user_by_email(email)
    if not user:
        return False
    key_hash = user["api_key_hash"]
    await client.collection(_USERS_COLLECTION).document(key_hash).update({
        "password_hash": hash_password(password),
    })
    _CACHE.pop(key_hash, None)
    return True


async def rotate_api_key(email: str) -> Optional[Dict[str, Any]]:
    """
    Issue a new API key for an existing user, replacing the old one.

    Implementation note: the Firestore doc id IS the api_key_hash, so we
    cannot just `update()` the field. We do it in two steps — write the new
    doc first (so there's never a window where the user has no record) and
    then delete the old doc. The old key keeps working for at most a few
    milliseconds, which is acceptable.

    Returns the user record with `api_key` populated (raw key — shown once)
    on success, or None when the user is missing / Firestore is unavailable.
    """
    client = _get_client()
    if client is None:
        return None
    user = await get_user_by_email(email)
    if not user:
        return None

    old_hash    = user["api_key_hash"]
    raw_key     = generate_api_key()
    new_hash    = hash_api_key(raw_key)
    new_record  = {**user, "api_key_hash": new_hash, "api_key_prefix": raw_key[:12]}

    # Write new, then delete old.
    await client.collection(_USERS_COLLECTION).document(new_hash).set(new_record)
    try:
        await client.collection(_USERS_COLLECTION).document(old_hash).delete()
    except Exception as exc:
        logger.warning("rotate_api_key: failed to delete old doc — %s", exc)

    # Refresh in-process cache: drop the old hash, install the new record.
    _CACHE.pop(old_hash, None)
    _CACHE[new_hash] = new_record
    logger.info("api_users: rotated key for %s — new prefix=%s", email, raw_key[:12])

    return {**new_record, "api_key": raw_key}


async def verify_credentials(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Look up a user by email and verify their password.
    Returns the (cache-fresh) user record on match, else None.
    """
    user = await get_user_by_email(email)
    if not user or user.get("revoked"):
        return None
    pw_hash = user.get("password_hash")
    if not pw_hash:
        return None  # user has no password set → cannot login
    if not verify_password(password, pw_hash):
        return None
    return user


def invalidate_cache(key_hash: Optional[str] = None) -> None:
    """Clear the per-process auth cache (single key or all)."""
    if key_hash:
        _CACHE.pop(key_hash, None)
    else:
        _CACHE.clear()
