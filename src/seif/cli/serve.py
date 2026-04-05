"""
seif serve (v1) bridge — read-only context API

Same pattern as serve_v2.py: open-source stub, proprietary implementation.
"""

try:
    from seif_engine.api.serve import run_server  # noqa: F401
except ImportError as e:
    raise ImportError(
        "seif serve requires SEIF Suite (seif-engine). "
        "Learn more: https://seifos.io"
    ) from e
