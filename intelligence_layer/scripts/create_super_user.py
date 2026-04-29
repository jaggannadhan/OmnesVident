"""
create_super_user.py — One-shot script to provision or update a privileged
account in the Firestore api_users collection.

Despite the historic name, the script can issue accounts at any access-level
combination supported by the model (`basic`, `super_user`, `admin`,
`premium`); pass `--levels` with a comma-separated list. Multiple levels are
permitted only when `admin` is one of them.

Usage:
    FIRESTORE_PROJECT=omnesvident \\
    .venv/bin/python -m intelligence_layer.scripts.create_super_user \\
        --name "Jagan" \\
        --email "jegsirox@gmail.com" \\
        --password "<password>" \\
        --levels "super_user,admin"

If the user already exists this idempotently:
  * sets/replaces the access_levels list to whatever was passed,
  * rotates the password (if `--password` provided),
  * leaves the API key intact (use `--rotate` to issue a fresh one).

The raw API key is printed to stdout EXACTLY ONCE for new users. Save it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Make the repo root importable when running as `python -m ...`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api_storage import api_users  # noqa: E402


def _parse_levels(raw: str) -> list[str]:
    return [s.strip().lower() for s in raw.split(",") if s.strip()]


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or update a privileged api_users record."
    )
    parser.add_argument("--name",  required=True, help="Display name")
    parser.add_argument("--email", required=True, help="Email (login identifier)")
    parser.add_argument(
        "--levels",
        default="super_user,admin",
        help="Comma-separated access levels. "
             f"Valid: {','.join(api_users.VALID_ACCESS_LEVELS)}. "
             "Multiple levels are permitted only when 'admin' is one of them. "
             "Default: 'super_user,admin'.",
    )
    parser.add_argument(
        "--password",
        help="Optional password (bcrypt-hashed before storage). "
             "Required for /v1/auth/login.  If the user already exists, "
             "this rotates the password without issuing a new API key.",
    )
    parser.add_argument(
        "--rotate", action="store_true",
        help="If user exists, delete and recreate so a fresh API key is issued.",
    )
    args = parser.parse_args()

    if not os.getenv("FIRESTORE_PROJECT"):
        print("ERROR: FIRESTORE_PROJECT env var is not set.", file=sys.stderr)
        print("Hint:  export FIRESTORE_PROJECT=omnesvident", file=sys.stderr)
        return 2

    levels = _parse_levels(args.levels)
    try:
        api_users.validate_access_levels(levels)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    existing = await api_users.get_user_by_email(args.email)

    if existing and not args.rotate:
        print("─── User already exists ───")
        print(f"  user_id        : {existing['user_id']}")
        print(f"  name           : {existing['name']}")
        print(f"  email          : {existing['email']}")
        print(f"  current levels : {existing.get('access_levels') or []}")
        print(f"  api_key_prefix : {existing['api_key_prefix']}…")

        ok = await api_users.set_access_levels(args.email, levels)
        print(f"\n→ access_levels set to {levels}: {ok}")
        if args.password:
            ok = await api_users.set_password(args.email, args.password)
            print(f"→ Password set/rotated: {ok}")
        print("\n(Pass --rotate to delete and recreate with a fresh API key.)")
        return 0

    if existing and args.rotate:
        # Delete the old doc so create_user can issue a fresh key
        client = api_users._get_client()
        if client is not None:
            await client.collection("api_users").document(existing["api_key_hash"]).delete()
            api_users.invalidate_cache(existing["api_key_hash"])
            print(f"→ Removed previous record for {args.email} (rotating key).")

    user = await api_users.create_user(
        name=args.name,
        email=args.email,
        password=args.password,
        access_levels=levels,
        # Unlimited tier when super_user or admin is granted, else default.
        rate_limit_per_min=0 if api_users.has_unlimited_access(levels) else None,
    )

    print("\n═══════════════════════════════════════════════════════════════════════")
    print("  USER CREATED — copy the API key now. It will not be shown again.")
    print("═══════════════════════════════════════════════════════════════════════\n")
    print(f"  Name          : {user['name']}")
    print(f"  Email         : {user['email']}")
    print(f"  User ID       : {user['user_id']}")
    print(f"  Access levels : {user['access_levels']}")
    rate = "unlimited" if api_users.has_unlimited_access(user["access_levels"]) else "default"
    print(f"  Rate limit    : {rate}")
    print(f"\n  API KEY       : {user['api_key']}\n")
    print("  Header to use : x-api-key: " + user["api_key"])
    print("\n  Quick test:")
    print(f"    curl -H 'x-api-key: {user['api_key']}' \\")
    print( "         'https://omnesvident-api-naqkmfs2qa-uc.a.run.app/v1/me'")
    print("\n═══════════════════════════════════════════════════════════════════════\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
