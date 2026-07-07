"""Compatibility shim; implementation in extract_server.grocery_extract.extract_worker."""
import sys

import extract_server.grocery_extract.extract_worker as _impl

sys.modules[__name__] = _impl
