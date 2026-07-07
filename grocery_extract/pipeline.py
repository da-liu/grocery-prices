"""Compatibility shim; implementation in extract_server.grocery_extract.pipeline."""
import sys

import extract_server.grocery_extract.pipeline as _impl

sys.modules[__name__] = _impl
