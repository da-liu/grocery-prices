"""Compatibility shim; implementation in extract_server.grocery_extract.ingest."""
import sys

import extract_server.grocery_extract.ingest as _impl

sys.modules[__name__] = _impl
