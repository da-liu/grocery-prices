"""Compatibility shim; implementation in extract_server.grocery_extract.logging_config."""
import sys

import extract_server.grocery_extract.logging_config as _impl

sys.modules[__name__] = _impl
