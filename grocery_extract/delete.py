"""Compatibility shim; implementation in extract_server.grocery_extract.delete."""
import sys

import extract_server.grocery_extract.delete as _impl

sys.modules[__name__] = _impl
