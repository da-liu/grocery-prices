"""Compatibility shim; implementation in extract_server.grocery_extract.user_paths."""
import sys

import extract_server.grocery_extract.user_paths as _impl

sys.modules[__name__] = _impl
