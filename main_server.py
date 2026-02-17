#!/usr/bin/env python3
"""Deprecated compatibility shim.

Use `admin_panel:app` as the canonical ASGI entrypoint.
"""

import warnings

import uvicorn
from admin_panel import app

warnings.warn(
    "`main_server.py` is deprecated. Use `admin_panel.py` (`admin_panel:app`) instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    uvicorn.run("admin_panel:app", host="127.0.0.1", port=8003, reload=False, access_log=True)
