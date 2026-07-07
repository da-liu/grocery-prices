"""Compatibility shim; implementation in extract_server.grocery_extract.prompt."""
import sys

import extract_server.grocery_extract.prompt as _impl

sys.modules[__name__] = _impl
