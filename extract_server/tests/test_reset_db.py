from __future__ import annotations

from pathlib import Path

from extract_server import users_db
from extract_server.scripts.reset_db import reset_all
from extract_server.users_db import get_conn, init_db, register_user
from grocery_extract.user_paths import user_root


def test_reset_all_clears_db_and_uploads(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GROCERY_DB_PATH", str(tmp_path / "grocery.db"))
    monkeypatch.setenv("GROCERY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("extract_server.db.connection.DB_PATH", tmp_path / "grocery.db")
    monkeypatch.setattr("grocery_extract.user_paths.DATA_DIR", tmp_path / "data")

    init_db()
    user = register_user("reset-test", "password123")
    photos_dir = user_root(user.id) / "photos" / "2026_07_06"
    photos_dir.mkdir(parents=True)
    (photos_dir / "IMG_0001.jpg").write_bytes(b"jpeg")

    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert photos_dir.exists()

    summary = reset_all()

    assert summary["removed_user_dirs"] == 1
    assert not (user_root(user.id)).exists()
    assert users_db.DB_PATH.exists()

    conn = get_conn()
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0] == 0
