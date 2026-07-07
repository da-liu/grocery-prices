"""Compatibility shim; implementation in extract_server.grocery_extract.errors."""
import sys

import extract_server.grocery_extract.errors as _impl

sys.modules[__name__] = _impl
