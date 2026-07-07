"""Compatibility shim; implementation in extract_server.grocery_extract.parse_response."""
import sys

import extract_server.grocery_extract.parse_response as _impl

sys.modules[__name__] = _impl
