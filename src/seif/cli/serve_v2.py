"""
seif serve --v2 bridge

This file is part of the open-source seif-cli.
The implementation lives in seif-engine (proprietary — part of SEIF Suite).

If seif-engine is not installed, wrapper.py catches the ImportError and
shows: "This feature requires SEIF Suite. Learn more: https://seifos.io"
"""

try:
    from seif_engine.api.serve_v2 import run_server_v2  # noqa: F401
except ImportError as e:
    raise ImportError(
        "seif serve --v2 requires SEIF Suite (seif-engine). "
        "Learn more: https://seifos.io"
    ) from e
