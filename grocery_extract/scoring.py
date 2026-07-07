"""Compatibility shim; implementation in extract_server.grocery_extract.scoring."""
import sys

import extract_server.grocery_extract.scoring as _impl

sys.modules[__name__] = _impl
