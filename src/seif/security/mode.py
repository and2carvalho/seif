"""
SEIF Mode — Development vs Production runtime behaviour.

Development: full metrics, quality gate on every interaction, classification audit,
             verbose logging, all assertions checked.
Production:  proxy classification only, minimal logging, no exhaustive checks.
             Optimized for throughput and minimal overhead.

Set via environment variable:
  SEIF_MODE=development  (default)
  SEIF_MODE=production

Or in .seif/config.json:
  {"mode": "production"}
"""

import os
import logging
from typing import Optional

logger = logging.getLogger("seif.security.mode")

# Valid modes
DEVELOPMENT = "development"
PRODUCTION = "production"
_VALID_MODES = {DEVELOPMENT, PRODUCTION}


def get_mode() -> str:
    """Get the current SEIF runtime mode.

    Priority:
      1. SEIF_MODE environment variable
      2. .seif/config.json "mode" field
      3. Default: development
    """
    env_mode = os.environ.get("SEIF_MODE", "").lower().strip()
    if env_mode in _VALID_MODES:
        return env_mode

    # Check config
    try:
        from seif.context.autonomous import find_context_repo, load_config
        repo = find_context_repo()
        if repo:
            config = load_config(repo)
            config_mode = config.get("mode", "").lower().strip()
            if config_mode in _VALID_MODES:
                return config_mode
    except Exception:
        pass

    return DEVELOPMENT


def is_development() -> bool:
    """True if running in development mode (full metrics)."""
    return get_mode() == DEVELOPMENT


def is_production() -> bool:
    """True if running in production mode (minimal overhead)."""
    return get_mode() == PRODUCTION


def should_measure() -> bool:
    """Should quality gate / classification audit run on this interaction?

    Development: always
    Production: never (proxy handles classification silently)
    """
    return is_development()


def should_log_verbose() -> bool:
    """Should detailed proxy/classification logs be emitted?"""
    return is_development()


def get_proxy_config() -> dict:
    """Get proxy configuration appropriate for current mode."""
    if is_production():
        return {
            "classify_all": True,       # Always classify (security critical)
            "log_classifications": False,  # No verbose logging
            "audit_on_send": False,     # No post-send audit
            "quality_gate": False,      # Skip quality measurement
            "metrics_collection": False,  # No dev metrics
            "fallback_on_timeout": "rule_based",  # Fast fallback
            "llm_timeout": 10,          # Short timeout (seconds)
        }
    else:
        return {
            "classify_all": True,
            "log_classifications": True,   # Full audit trail
            "audit_on_send": True,      # Verify after sending
            "quality_gate": True,       # Measure every interaction
            "metrics_collection": True,   # Collect for baseline
            "fallback_on_timeout": "rule_based",
            "llm_timeout": 30,          # More patient in dev
        }
