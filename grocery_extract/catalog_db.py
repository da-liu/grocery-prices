"""Compatibility shim; implementation in extract_server.db."""
import sys

import extract_server.db as _impl

sys.modules[__name__] = _impl
