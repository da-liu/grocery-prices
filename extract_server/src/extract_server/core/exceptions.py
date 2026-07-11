from __future__ import annotations


class GroceryError(Exception):
    """Base domain error for grocery-prices backend."""


class ConfigError(GroceryError):
    """Missing or invalid service configuration (maps to HTTP 503)."""


class ExtractionError(GroceryError):
    """Vision LLM or extraction pipeline failure (maps to HTTP 502)."""
