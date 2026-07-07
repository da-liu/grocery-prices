"""Compatibility shim; implementation in extract_server.grocery_extract.photo_stores."""
import sys

import extract_server.grocery_extract.photo_stores as _impl

sys.modules[__name__] = _impl
