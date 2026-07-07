"""Compatibility shim; implementation in extract_server.db.user_stores."""
import sys

import extract_server.db.user_stores as _impl

sys.modules[__name__] = _impl
