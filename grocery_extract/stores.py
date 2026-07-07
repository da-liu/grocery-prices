"""Compatibility shim; implementation in extract_server.grocery_extract.stores."""
import sys

import extract_server.grocery_extract.stores as _impl

sys.modules[__name__] = _impl
