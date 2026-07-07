#!/usr/bin/env python3
"""Delete the SQLite catalog and all uploaded user files, then recreate an empty schema."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from extract_server.db import close_all_connections, db_path, init_db
from extract_server.extraction import paths as user_paths

LAUNCHD_LABEL = "com.daliu.grocery-prices.api"
DEFAULT_API_PORT = int(os.environ.get("GROCERY_API_PORT", "8765"))
_EXTRACT_SERVER_DIR = Path(__file__).resolve().parents[1]
_START_SCRIPT = _EXTRACT_SERVER_DIR / "start.sh"


def reset_all() -> dict[str, str | int]:
    """Remove DB + uploaded files and re-init schema. Returns summary counts."""
    db_path_val = db_path().resolve()
    users_dir = (user_paths.data_dir() / "users").resolve()

    close_all_connections()

    removed_db_files = 0
    for path in (db_path_val, Path(f"{db_path_val}-wal"), Path(f"{db_path_val}-shm")):
        if path.exists():
            path.unlink()
            removed_db_files += 1

    removed_user_dirs = 0
    if users_dir.exists():
        for child in users_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
                removed_user_dirs += 1
            else:
                child.unlink()
    users_dir.mkdir(parents=True, exist_ok=True)

    init_db()

    return {
        "db_path": str(db_path_val),
        "users_dir": str(users_dir),
        "removed_db_files": removed_db_files,
        "removed_user_dirs": removed_user_dirs,
    }


def _launchd_service_name() -> str:
    return f"gui/{os.getuid()}/{LAUNCHD_LABEL}"


def _launchd_service_loaded() -> bool:
    result = subprocess.run(
        ["launchctl", "print", _launchd_service_name()],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _pids_on_port(port: int) -> list[int]:
    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [int(pid) for pid in result.stdout.split() if pid.strip()]


def _wait_for_health(port: int, *, timeout_s: float = 15) -> bool:
    deadline = time.monotonic() + timeout_s
    url = f"http://127.0.0.1:{port}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    return False


def restart_api(*, port: int = DEFAULT_API_PORT) -> str:
    """Restart the grocery API and wait for /health. Returns how it was restarted."""
    if _launchd_service_loaded():
        subprocess.run(
            ["launchctl", "kickstart", "-k", _launchd_service_name()],
            check=True,
        )
        method = "launchd"
    else:
        for pid in _pids_on_port(port):
            os.kill(pid, signal.SIGTERM)
        if _pids_on_port(port):
            time.sleep(0.5)
            for pid in _pids_on_port(port):
                os.kill(pid, signal.SIGKILL)

        env = os.environ.copy()
        subprocess.Popen(
            ["/bin/bash", str(_START_SCRIPT)],
            cwd=_EXTRACT_SERVER_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        method = "start.sh"

    if not _wait_for_health(port):
        raise RuntimeError(f"API did not become healthy on port {port}")

    return method


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Confirm destructive reset (required)",
    )
    parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Skip restarting the API after reset",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    db_path_val = db_path().resolve()
    users_dir = (user_paths.data_dir() / "users").resolve()

    if not args.yes:
        print("This will permanently delete:", file=sys.stderr)
        print(f"  database: {db_path_val}", file=sys.stderr)
        print(f"  uploads:  {users_dir}/*", file=sys.stderr)
        if not args.no_restart:
            print(f"  api:      restart service on port {DEFAULT_API_PORT}", file=sys.stderr)
        print("Re-run with --yes to proceed.", file=sys.stderr)
        return 1

    try:
        summary = reset_all()
    finally:
        close_all_connections()

    print(f"Reset database at {summary['db_path']}")
    print(f"Cleared uploads under {summary['users_dir']}")
    print(
        f"Removed {summary['removed_db_files']} db file(s) "
        f"and {summary['removed_user_dirs']} user director(ies)"
    )

    if args.no_restart:
        print("Skipped API restart (--no-restart)")
        return 0

    try:
        method = restart_api()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as err:
        print(f"API restart failed: {err}", file=sys.stderr)
        return 1

    print(f"Restarted API via {method} (http://127.0.0.1:{DEFAULT_API_PORT}/health)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
