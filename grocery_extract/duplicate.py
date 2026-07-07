"""Compatibility shim; implementation in extract_server.grocery_extract.duplicate."""
import sys

import extract_server.grocery_extract.duplicate as _impl

sys.modules[__name__] = _impl
