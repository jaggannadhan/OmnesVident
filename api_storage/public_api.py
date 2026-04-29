"""
public_api.py — Versioned public REST API (mounted at /v1).

External consumers authenticate with an `x-api-key` header. A user obtains a
key by signing up at POST /v1/auth/signup. Each key carries:

  * an access_level ("super-user" or "community")
  * an optional rate_limit_per_min override (0 = unlimited)

Default rate limits:
    super-user      → unlimited
    community       → 5 requests / minute  (per key, per Cloud Run instance)

Endpoints:
    POST /v1/auth/signup        — create user + issue key (one-time)
    GET  /v1/me                 — verify key, return user info (no quota cost)
    GET  /v1/stories            — paginated story query, all filters
    GET  /v1/stories/{doc_id}   — single story
    GET  /v1/breaking           — convenience: is_breaking=true, sorted by heat
    GET  /v1/regions            — list of supported region codes
    GET  /v1/categories         — list of category codes + labels
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from api_storage.api_users import (
    create_user,
    get_user_by_email,
    get_user_by_key_hash,
    hash_api_key,
    has_unlimited_access,
    rotate_api_key,
    verify_credentials,
)
from api_storage.login_throttle import (
    check_login_allowed,
    record_failure as record_login_failure,
    record_success as record_login_success,
)
from api_storage.rate_limiter import limiter
from api_storage.schemas import PaginatedStoriesResponse, StoryOut
from api_storage import session_tokens

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Public API v1"])


# ─── Categories & regions (static reference data) ────────────────────────────

_CATEGORIES: List[Dict[str, str]] = [
    {"code": "WORLD",         "label": "World"},
    {"code": "POLITICS",      "label": "Politics"},
    {"code": "SCIENCE_TECH",  "label": "Science & Tech"},
    {"code": "BUSINESS",      "label": "Business"},
    {"code": "HEALTH",        "label": "Health"},
    {"code": "ENTERTAINMENT", "label": "Entertainment"},
    {"code": "SPORTS",        "label": "Sports"},
]


# ─── Auth & rate-limit dependency ────────────────────────────────────────────

class _AuthedUser(BaseModel):
    user_id:        str
    name:           str
    email:          str
    access_levels:  List[str]
    api_key_prefix: str
    rate_limit_per_min: Optional[int] = None


async def auth_required(
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
) -> _AuthedUser:
    """FastAPI dependency: validate x-api-key, enforce rate limit."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-api-key header. Sign up at /api-docs to get a key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = hash_api_key(x_api_key.strip())
    user = await get_user_by_key_hash(key_hash)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
        )

    levels = user.get("access_levels") or []
    is_unlimited = has_unlimited_access(levels)
    user_rate = user.get("rate_limit_per_min")
    allowed = limiter.acquire(
        key=key_hash,
        rate_per_min=user_rate,
        unlimited=is_unlimited,
    )
    if not allowed:
        retry = limiter.retry_after_seconds(key_hash)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry in {retry}s.",
            headers={"Retry-After": str(retry)},
        )

    return _AuthedUser(
        user_id=user["user_id"],
        name=user["name"],
        email=user["email"],
        access_levels=list(levels),
        api_key_prefix=user["api_key_prefix"],
        rate_limit_per_min=user_rate,
    )


# ─── Schemas — signup ────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name:     str = Field(..., min_length=2, max_length=80)
    email:    EmailStr
    password: str = Field(..., min_length=8, max_length=128,
                          description="Stored as a bcrypt hash; never persisted in plaintext.")

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, v: str) -> str:
        """Defense-in-depth: enforce the same rules the UI shows users."""
        if not re.search(r"[A-Z]",     v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]",     v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d",        v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[^A-Za-z0-9]", v):
            raise ValueError("Password must contain at least one special character.")
        return v


class SignupResponse(BaseModel):
    user_id:        str
    name:           str
    email:          str
    access_levels:  List[str]
    api_key:        str = Field(..., description="Save this — it is shown ONCE.")
    api_key_prefix: str
    rate_limit_per_min: Optional[int]
    session_token:  Optional[str] = Field(
        None,
        description="Bearer token for user-action endpoints (regenerate-key, etc.)."
    )
    notice: str = (
        "This API key is shown only once. Store it in a secret manager. "
        "If you lose it, log in and click 'Regenerate API key'."
    )


class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    user_id:        str
    name:           str
    email:          str
    access_levels:  List[str]
    api_key_prefix: str
    rate_limit_per_min: Optional[int]
    session_token:  Optional[str] = Field(
        None,
        description="Bearer token for user-action endpoints (regenerate-key, etc.)."
    )


class RegenerateKeyResponse(BaseModel):
    user_id:        str
    email:          str
    api_key:        str = Field(..., description="The freshly minted key. Shown ONCE.")
    api_key_prefix: str
    notice: str = (
        "Your previous API key has been invalidated. Save this new key now — "
        "we cannot retrieve it later."
    )


# ─── Routes — auth ───────────────────────────────────────────────────────────

@router.post("/auth/signup", response_model=SignupResponse, status_code=201)
async def signup(req: SignupRequest):
    """Create a basic-tier user and return a fresh API key (one time only).
    Stores the password as a bcrypt hash so the user can later authenticate via
    /v1/auth/login without us ever seeing the raw password again.

    All public signups land at access_levels=['basic']. Premium / super_user /
    admin promotions happen out-of-band (admin script or admin endpoint)."""
    try:
        user = await create_user(
            name=req.name,
            email=str(req.email),
            password=req.password,
            access_levels=["basic"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:
        logger.error("signup: backend not configured — %s", exc)
        raise HTTPException(status_code=503, detail="User store unavailable. Try again later.")

    return SignupResponse(
        user_id=user["user_id"],
        name=user["name"],
        email=user["email"],
        access_levels=user["access_levels"],
        api_key=user["api_key"],
        api_key_prefix=user["api_key_prefix"],
        rate_limit_per_min=user.get("rate_limit_per_min"),
        session_token=session_tokens.issue(user["user_id"], user["email"]),
    )


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Verify email + password (bcrypt) and return user metadata.

    For privacy reasons we deliberately do NOT return the raw API key — keys
    are stored as a SHA-256 hash and cannot be recovered. The frontend uses
    this to populate the UI with the logged-in user's identity; programmatic
    API calls still require the raw key the user saved at signup time.

    Returns 401 with a generic message regardless of whether the email exists,
    so an attacker cannot enumerate valid emails.

    Per-email failed-login throttling kicks in after 5 strikes in 15 min,
    returning 429 with a `Retry-After` header. We throttle based on the email
    we received — including emails that don't exist — so 429 responses cannot
    be used to enumerate registered accounts.
    """
    email_lc = str(req.email).strip().lower()

    # Throttle BEFORE we even attempt the bcrypt check — bcrypt is slow on
    # purpose, and we don't want an attacker to use it as an oracle.
    retry_after = check_login_allowed(email_lc)
    if retry_after > 0:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    user = await verify_credentials(email_lc, req.password)
    if not user:
        record_login_failure(email_lc)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    record_login_success(email_lc)
    return LoginResponse(
        user_id=user["user_id"],
        name=user["name"],
        email=user["email"],
        access_levels=user.get("access_levels") or ["basic"],
        api_key_prefix=user["api_key_prefix"],
        rate_limit_per_min=user.get("rate_limit_per_min"),
        session_token=session_tokens.issue(user["user_id"], user["email"]),
    )


@router.post("/auth/regenerate-key", response_model=RegenerateKeyResponse)
async def regenerate_key(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """
    Issue a new API key for the calling user, invalidating the previous one.

    Authentication: `Authorization: Bearer <session_token>`. The session token
    is the value the frontend received from `/v1/auth/login` or
    `/v1/auth/signup`. We deliberately do NOT accept x-api-key here — if your
    key is compromised, you'd want to be able to rotate it without sending
    the compromised key.

    The new raw key is returned in the body. Store it; we cannot recover it.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <session_token>.",
        )
    token = authorization.split(" ", 1)[1].strip()
    payload = session_tokens.verify(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )

    user = await get_user_by_email(payload["email"])
    if not user or user.get("user_id") != payload["uid"] or user.get("revoked"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account no longer accessible.",
        )

    rotated = await rotate_api_key(payload["email"])
    if not rotated:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not rotate key — try again shortly.",
        )

    return RegenerateKeyResponse(
        user_id=rotated["user_id"],
        email=rotated["email"],
        api_key=rotated["api_key"],
        api_key_prefix=rotated["api_key_prefix"],
    )


@router.get("/me", response_model=_AuthedUser)
async def me(user: _AuthedUser = Depends(auth_required)):
    """Verify the supplied key and echo back identity. Useful for client setup."""
    return user


# ─── Routes — reference data ─────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(_: _AuthedUser = Depends(auth_required)):
    return {"categories": _CATEGORIES}


@router.get("/regions")
async def list_regions(_: _AuthedUser = Depends(auth_required)):
    """Return supported region codes from regions_to_track.json."""
    import json
    from pathlib import Path
    regions_path = Path(__file__).resolve().parent.parent / "ingestion_engine" / "regions_to_track.json"
    try:
        with open(regions_path, encoding="utf-8") as f:
            data = json.load(f)
        flat: List[Dict[str, str]] = []
        for country, regions in data.items():
            for r in regions:
                flat.append({"country": country, "code": r["code"], "name": r["name"]})
        return {"count": len(flat), "regions": flat}
    except Exception as exc:
        logger.error("list_regions failed: %s", exc)
        raise HTTPException(status_code=500, detail="Region catalog unavailable.")


# ─── Routes — stories ────────────────────────────────────────────────────────

# Shared filter helper so /stories and /breaking stay DRY
async def _query(
    *,
    region: Optional[str],
    category: Optional[str],
    country: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    is_breaking: Optional[bool],
    min_heat_score: Optional[int],
    limit: int,
    offset: int,
) -> PaginatedStoriesResponse:
    """Query Firestore master_news with optional post-filters for breaking + heat."""
    from database.firestore_manager import firestore_manager
    from api_storage.routes import _firestore_doc_to_story_out  # reuse mapper

    if not firestore_manager._is_enabled():
        raise HTTPException(status_code=503, detail="Story backend unavailable.")

    # Default window: last 7 days for the public API (more useful for external clients)
    effective_start = start_date or (datetime.now(tz=timezone.utc) - timedelta(days=7))
    effective_end = end_date

    region_filter = region
    if country and not region_filter:
        region_filter = country.upper()

    # We may need to over-fetch when post-filtering by is_breaking / min_heat_score,
    # because Firestore can't index every combination. Cap the over-fetch to keep
    # latency bounded.
    needs_post_filter = is_breaking is True or (min_heat_score is not None and min_heat_score > 0)
    fetch_limit = limit if not needs_post_filter else min(limit * 5, 1000)

    docs = await firestore_manager.query_master_by_timestamp(
        region_code=region_filter,
        category=category.upper() if category else None,
        start_dt=effective_start,
        end_dt=effective_end,
        limit=fetch_limit,
        offset=offset if not needs_post_filter else 0,
    )

    stories = [_firestore_doc_to_story_out(d) for d in docs]

    if is_breaking is True:
        stories = [s for s in stories if s.is_breaking]
    if min_heat_score is not None and min_heat_score > 0:
        stories = [s for s in stories if s.heat_score >= min_heat_score]

    if needs_post_filter:
        # Apply offset/limit AFTER post-filtering
        sliced = stories[offset:offset + limit]
        return PaginatedStoriesResponse(
            total=len(stories), offset=offset, limit=limit, stories=sliced
        )

    total = await firestore_manager.count_master_by_timestamp(
        region_code=region_filter,
        category=category.upper() if category else None,
        start_dt=effective_start,
        end_dt=effective_end,
    )
    if total < 0:
        total = offset + len(stories) + (1 if len(stories) == limit else 0)
    return PaginatedStoriesResponse(
        total=total, offset=offset, limit=limit, stories=stories
    )


@router.get("/stories", response_model=PaginatedStoriesResponse)
async def get_stories(
    region:         Optional[str]   = Query(None, description="Region filter (e.g. IN-TN, US-CA, or country code IN)"),
    category:       Optional[str]   = Query(None, description="One of: WORLD, POLITICS, SCIENCE_TECH, BUSINESS, HEALTH, ENTERTAINMENT, SPORTS"),
    country:        Optional[str]   = Query(None, description="Two-letter country code (alias for region when no subdivision is given)"),
    start_date:     Optional[datetime] = Query(None, description="ISO 8601, inclusive lower bound. Defaults to 7 days ago."),
    end_date:       Optional[datetime] = Query(None, description="ISO 8601, inclusive upper bound."),
    is_breaking:    Optional[bool]  = Query(None, description="If true, only breaking-news stories."),
    min_heat_score: Optional[int]   = Query(None, ge=0, le=100, description="Filter to stories with heat_score >= this value."),
    limit:          int             = Query(50, ge=1, le=200),
    offset:         int             = Query(0, ge=0),
    _:              _AuthedUser     = Depends(auth_required),
):
    """
    Paginated story search.

    Example — Tamil Nadu politics:
        GET /v1/stories?region=IN-TN&category=POLITICS

    Example — global breaking health news:
        GET /v1/stories?category=HEALTH&is_breaking=true
    """
    return await _query(
        region=region, category=category, country=country,
        start_date=start_date, end_date=end_date,
        is_breaking=is_breaking, min_heat_score=min_heat_score,
        limit=limit, offset=offset,
    )


@router.get("/breaking", response_model=PaginatedStoriesResponse)
async def breaking_stories(
    region:   Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit:    int           = Query(20, ge=1, le=100),
    _:        _AuthedUser   = Depends(auth_required),
):
    """Convenience: stories with is_breaking=true in the last 24h, by heat_score desc."""
    result = await _query(
        region=region, category=category, country=None,
        start_date=datetime.now(tz=timezone.utc) - timedelta(hours=24),
        end_date=None,
        is_breaking=True, min_heat_score=None,
        limit=limit, offset=0,
    )
    result.stories.sort(key=lambda s: s.heat_score, reverse=True)
    return result


_DOC_ID_RE = re.compile(r"^[a-f0-9]{16,32}$")


@router.get("/stories/{doc_id}", response_model=StoryOut)
async def get_story(doc_id: str, _: _AuthedUser = Depends(auth_required)):
    """Fetch a single story by its Firestore document ID."""
    if not _DOC_ID_RE.match(doc_id):
        raise HTTPException(status_code=400, detail="Malformed story id.")

    from database.firestore_manager import firestore_manager
    from api_storage.routes import _firestore_doc_to_story_out

    if not firestore_manager._is_enabled():
        raise HTTPException(status_code=503, detail="Story backend unavailable.")

    client = await firestore_manager._get_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Story backend unavailable.")

    snap = await client.collection("master_news").document(doc_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Story not found.")
    data = snap.to_dict() or {}
    data["_doc_id"] = snap.id
    return _firestore_doc_to_story_out(data)
