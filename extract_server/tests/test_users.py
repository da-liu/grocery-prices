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
_BULK_TEST_EMAIL_RE = re.compile(r"^bulk-test-\d+@example\.com$")


def is_test_username(username: str) -> bool:
    username = username.strip().lower()
    return (
        username in KNOWN_TEST_USERNAMES
        or bool(_STORES_USERNAME_RE.match(username))
        or bool(_BULK_TEST_EMAIL_RE.match(username))
    )
