"""Compatibility shim; implementation in extract_server.grocery_extract.schema."""
import sys

import extract_server.grocery_extract.schema as _impl

sys.modules[__name__] = _impl
