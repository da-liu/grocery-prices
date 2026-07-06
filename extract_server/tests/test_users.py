"""Usernames created by extract_server/tests/test_api.py."""

from __future__ import annotations

import re

KNOWN_TEST_USERNAMES = frozenset(
    {
        "alice@example.com",
        "bulk-uploader",
        "testuser",
        "uploader",
        "deleter",
        "bulkdeleter",
        "onboarded",
    }
)

_STORES_USERNAME_RE = re.compile(r"^stores_[a-f0-9]{8}$")
_EXTRACT_TEST_RE = re.compile(r"^extract_test_\d+$")
_DELETEUSER_RE = re.compile(r"^deleteuser_[a-f0-9]{8}$")
_STORES_MERGE_RE = re.compile(r"^stores_merge_[a-f0-9]{8}$")


def is_test_username(username: str) -> bool:
    username = username.strip().lower()
    return (
        username in KNOWN_TEST_USERNAMES
        or username.endswith("@example.com")
        or bool(_STORES_USERNAME_RE.match(username))
        or bool(_EXTRACT_TEST_RE.match(username))
        or bool(_DELETEUSER_RE.match(username))
        or bool(_STORES_MERGE_RE.match(username))
    )
