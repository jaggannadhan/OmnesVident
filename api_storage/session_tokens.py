"""
session_tokens.py — Stateless HMAC-signed session tokens for the public API.

Used by `/v1/auth/login` and `/v1/auth/signup` to issue a short-lived bearer
token that the frontend can present (via `Authorization: Bearer <token>`)
on user-action endpoints like `/v1/auth/regenerate-key` — without us having
to keep server-side session state.

Format
------
A token is `<payload>.<signature>` where:

  payload   = base64url(json({
                "uid":   user_id,
                "email": email,
                "exp":   epoch_seconds_when_token_expires,
              }))
  signature = base64url(HMAC-SHA256(SESSION_SECRET, payload))

Verification re-computes the signature in constant time, then checks the
`exp` claim. No JSON-Web-Token library required — stdlib only.

Configuration
-------------
SESSION_SECRET (env var)   — HMAC key. If unset, falls back to INGEST_SECRET
                             (which Cloud Run already has). Either MUST be
                             set in production; absent both, token issuance
                             is disabled and the regenerate endpoint will
                             reject all requests.
SESSION_TTL_SECONDS (env)  — default 86400 (24h).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class SessionPayload(TypedDict):
    uid:   str
    email: str
    exp:   int


def _secret() -> bytes:
    s = os.getenv("SESSION_SECRET") or os.getenv("INGEST_SECRET") or ""
    return s.encode("utf-8")


def _ttl() -> int:
    try:
        return int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    except ValueError:
        return 86400


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue(user_id: str, email: str) -> Optional[str]:
    """Mint a session token for a user. Returns None if no secret is configured."""
    secret = _secret()
    if not secret:
        logger.warning("session_tokens.issue: no SESSION_SECRET/INGEST_SECRET set; skipping.")
        return None
    payload: SessionPayload = {
        "uid":   user_id,
        "email": email.lower(),
        "exp":   int(time.time()) + _ttl(),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig  = _b64encode(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str) -> Optional[SessionPayload]:
    """
    Verify a session token. Returns the payload on success, None otherwise.

    A None return covers all failure modes (missing secret, malformed, bad
    signature, expired). Callers MUST treat None as 401.
    """
    secret = _secret()
    if not secret or not token:
        return None
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError:
        return None

    expected = hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest()
    actual   = _b64decode(sig)
    # constant-time comparison to defeat timing attacks
    if not hmac.compare_digest(expected, actual):
        return None

    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    if not isinstance(payload.get("uid"), str) or not isinstance(payload.get("email"), str):
        return None
    return payload  # type: ignore[return-value]
