#!/usr/bin/env python3
"""Remove test users left in the production DB and extract_server/data/users/ by old test runs."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extract_server.users_db import DB_PATH  # noqa: E402
from grocery_extract.user_paths import user_root  # noqa: E402
from tests.test_users import is_test_username  # noqa: E402


def find_test_users(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute("SELECT id, username FROM users").fetchall()
    return [(row["id"], row["username"]) for row in rows if is_test_username(row["username"])]


def delete_test_user(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM user_store_locations WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def remove_user_data(user_id: str, *, dry_run: bool) -> bool:
    directory = user_root(user_id)
    if not directory.exists():
        return False
    if dry_run:
        print(f"  would remove {directory}")
    else:
        shutil.rmtree(directory)
        print(f"  removed {directory}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    args = parser.parse_args()
    dry_run = not args.execute

    if dry_run:
        print("Dry run (pass --execute to apply)\n")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    test_users = find_test_users(conn)

    if not test_users:
        print("No test users found.")
        return 0

    print(f"Database: {DB_PATH}")
    for user_id, username in test_users:
        print(f"- {username} ({user_id})")

    if dry_run:
        for user_id, _username in test_users:
            remove_user_data(user_id, dry_run=True)
        print(f"\nWould delete {len(test_users)} user(s) from the database.")
        return 0

    with conn:
        for user_id, _username in test_users:
            delete_test_user(conn, user_id)
    conn.close()

    removed_dirs = 0
    for user_id, _username in test_users:
        if remove_user_data(user_id, dry_run=False):
            removed_dirs += 1

    print(f"\nDeleted {len(test_users)} user(s) from the database.")
    print(f"Removed {removed_dirs} data directory(ies).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
