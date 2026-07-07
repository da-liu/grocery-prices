"""Compatibility shim; implementation in extract_server.grocery_extract.cursor_extractor."""
import sys

import extract_server.grocery_extract.cursor_extractor as _impl

sys.modules[__name__] = _impl
