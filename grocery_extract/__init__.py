"""Grocery price photo extraction pipeline."""

import sys

import extract_server.grocery_extract as _impl

sys.modules[__name__] = _impl
