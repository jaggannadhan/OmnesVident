"""
create_super_user.py — One-shot script to provision a super-user account
in the Firestore api_users collection.

Usage:
    FIRESTORE_PROJECT=omnesvident \
    .venv/bin/python -m intelligence_layer.scripts.create_super_user \
        --name "Jagan" --email "jegsirox@gmail.com"

If the user already exists, this script idempotently upgrades them to
super-user (zero rate-limit) and prints the existing key prefix without
re-issuing. To force a brand-new key, pass --rotate.

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


async def main() -> int:
    parser = argparse.ArgumentParser(description="Create or upgrade a super-user.")
    parser.add_argument("--name",  required=True, help="Display name")
    parser.add_argument("--email", required=True, help="Email (also the login key)")
    parser.add_argument(
        "--rotate", action="store_true",
        help="If user exists, delete and recreate so a fresh key is issued.",
    )
    args = parser.parse_args()

    if not os.getenv("FIRESTORE_PROJECT"):
        print("ERROR: FIRESTORE_PROJECT env var is not set.", file=sys.stderr)
        print("Hint:  export FIRESTORE_PROJECT=omnesvident", file=sys.stderr)
        return 2

    existing = await api_users.get_user_by_email(args.email)

    if existing and not args.rotate:
        print("─── User already exists ───")
        print(f"  user_id        : {existing['user_id']}")
        print(f"  name           : {existing['name']}")
        print(f"  email          : {existing['email']}")
        print(f"  current level  : {existing.get('access_level')}")
        print(f"  api_key_prefix : {existing['api_key_prefix']}…")
        if existing.get("access_level") != "super-user":
            ok = await api_users.upgrade_to_super_user(args.email)
            print(f"\n→ Upgraded to super-user: {ok}")
        else:
            print("\n→ Already a super-user. No changes.")
        print("\n(Pass --rotate to delete and recreate with a fresh key.)")
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
        access_level="super-user",
        rate_limit_per_min=0,   # 0 = unlimited
    )

    print("\n═══════════════════════════════════════════════════════════════════════")
    print("  SUPER-USER CREATED — copy the API key now. It will not be shown again.")
    print("═══════════════════════════════════════════════════════════════════════\n")
    print(f"  Name          : {user['name']}")
    print(f"  Email         : {user['email']}")
    print(f"  User ID       : {user['user_id']}")
    print(f"  Access level  : {user['access_level']}")
    print(f"  Rate limit    : unlimited")
    print(f"\n  API KEY       : {user['api_key']}\n")
    print("  Header to use : x-api-key: " + user["api_key"])
    print("\n  Quick test:")
    print(f"    curl -H 'x-api-key: {user['api_key']}' \\")
    print( "         'https://omnesvident-api-naqkmfs2qa-uc.a.run.app/v1/me'")
    print("\n═══════════════════════════════════════════════════════════════════════\n")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
