#!/usr/bin/env python3
"""Remove a registered user and their on-disk data directory."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from extract_server.users_db import close_all_connections, get_conn, get_user_by_id
from grocery_extract.user_paths import user_root


def remove_registered_user(user_id: str, *, remove_files: bool = True) -> bool:
    user = get_user_by_id(user_id)
    if user is None:
        return False

    conn = get_conn()
    conn.execute("DELETE FROM user_store_locations WHERE user_id = ?", (user_id,))
    deleted = conn.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount
    if deleted == 0:
        return False

    if remove_files:
        user_dir = user_root(user_id)
        if user_dir.exists():
            shutil.rmtree(user_dir)

    return True


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", help="User id (uuid hex) to remove")
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Remove DB rows only; leave data/users/<id> on disk",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        removed = remove_registered_user(args.user_id, remove_files=not args.keep_files)
    finally:
        close_all_connections()

    if not removed:
        print(f"User not found: {args.user_id}", file=sys.stderr)
        return 1
    print(f"Removed user {args.user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
