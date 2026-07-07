"""Compatibility shim; implementation in extract_server.grocery_extract.request_context."""
import sys

import extract_server.grocery_extract.request_context as _impl

sys.modules[__name__] = _impl
