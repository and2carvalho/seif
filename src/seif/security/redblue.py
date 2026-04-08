"""
Red/Blue team security assessment.

Requires seif-engine (optional dependency). When seif-engine is not installed
(e.g. pip install seif-cli without [security] extra), imports are stubbed
so the public package doesn't crash on import.
"""

try:
    from seif_engine.security.redblue import (
        red_team_test,
        blue_team_audit,
        run_full_assessment,
        security_score,
        RedTeamResult,
        RedTeamReport,
        BlueTeamAudit,
        SecurityScore,
        DEFAULT_RED_VECTORS,
    )
except ImportError:
    # seif-engine not installed — provide stubs that raise helpful errors
    def _not_available(*_a, **_kw):
        raise RuntimeError(
            "Red/Blue team requires seif-engine. "
            "Install with: pip install seif-engine"
        )

    red_team_test = _not_available
    blue_team_audit = _not_available
    run_full_assessment = _not_available
    security_score = _not_available
    RedTeamResult = type("RedTeamResult", (), {})
    RedTeamReport = type("RedTeamReport", (), {})
    BlueTeamAudit = type("BlueTeamAudit", (), {})
    SecurityScore = type("SecurityScore", (), {})
    DEFAULT_RED_VECTORS = []

__all__ = [
    "red_team_test",
    "blue_team_audit",
    "run_full_assessment",
    "security_score",
    "RedTeamResult",
    "RedTeamReport",
    "BlueTeamAudit",
    "SecurityScore",
    "DEFAULT_RED_VECTORS",
]
