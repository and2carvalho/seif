"""
Bridge to seif-engine native chat.

This module exists in seif-cli so that 
works when seif-engine is installed. The actual implementation lives in
seif_engine.api.chat (proprietary / Pro tier).
"""

from seif_engine.api.chat import run_chat  # noqa: F401

__all__ = ["run_chat"]
