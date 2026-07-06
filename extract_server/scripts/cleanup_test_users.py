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
from grocery_extract.user_paths import DATA_DIR, user_root  # noqa: E402
from tests.test_users import is_test_username  # noqa: E402


def find_test_users(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute("SELECT id, username FROM users").fetchall()
    return [(row["id"], row["username"]) for row in rows if is_test_username(row["username"])]


def find_orphan_user_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT user_id FROM (
            SELECT user_id FROM photos
            UNION SELECT user_id FROM product_sightings
            UNION SELECT user_id FROM extractions
            UNION SELECT user_id FROM user_store_locations
        )
        WHERE user_id NOT IN (SELECT id FROM users)
        ORDER BY user_id
        """
    ).fetchall()
    return [row["user_id"] for row in rows]


def find_stray_user_dirs(conn: sqlite3.Connection) -> list[Path]:
    users_dir = DATA_DIR / "users"
    if not users_dir.is_dir():
        return []
    known_ids = {row["id"] for row in conn.execute("SELECT id FROM users")}
    return sorted(
        path
        for path in users_dir.iterdir()
        if path.is_dir() and path.name not in known_ids
    )


def delete_orphan_catalog_rows(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM photos WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM user_store_locations WHERE user_id = ?", (user_id,))


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


def remove_user_data_path(directory: Path, *, dry_run: bool) -> bool:
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
    conn.execute("PRAGMA foreign_keys = ON")
    test_users = find_test_users(conn)
    orphan_user_ids = find_orphan_user_ids(conn)
    stray_dirs = find_stray_user_dirs(conn)

    if not test_users and not orphan_user_ids and not stray_dirs:
        print("No test users or stray user data found.")
        conn.close()
        return 0

    print(f"Database: {DB_PATH}")

    if test_users:
        print("\nTest users:")
        for user_id, username in test_users:
            print(f"- {username} ({user_id})")

    if orphan_user_ids:
        print("\nOrphan catalog rows:")
        for user_id in orphan_user_ids:
            print(f"- {user_id}")

    if stray_dirs:
        print("\nStray data directories:")
        for directory in stray_dirs:
            print(f"- {directory}")

    if dry_run:
        for user_id, _username in test_users:
            remove_user_data(user_id, dry_run=True)
        for directory in stray_dirs:
            remove_user_data_path(directory, dry_run=True)
        print(
            f"\nWould delete {len(test_users)} user(s), "
            f"purge {len(orphan_user_ids)} orphan catalog user(s), "
            f"and remove {len(stray_dirs)} stray data directory(ies)."
        )
        conn.close()
        return 0

    with conn:
        for user_id, _username in test_users:
            delete_test_user(conn, user_id)
        for user_id in orphan_user_ids:
            delete_orphan_catalog_rows(conn, user_id)
    conn.close()

    removed_dirs = 0
    for user_id, _username in test_users:
        if remove_user_data(user_id, dry_run=False):
            removed_dirs += 1
    for directory in stray_dirs:
        if remove_user_data_path(directory, dry_run=False):
            removed_dirs += 1

    print(f"\nDeleted {len(test_users)} user(s) from the database.")
    print(f"Purged catalog rows for {len(orphan_user_ids)} orphan user(s).")
    print(f"Removed {removed_dirs} data directory(ies).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
