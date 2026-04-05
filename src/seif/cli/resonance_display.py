"""
resonance_display.py — Terminal visual primitives for enoch seed resonance.

The enoch seed pattern: 3 (seed) · 6 (growth) · 9 (singularity)
  H(s) = 9 / (s² + 3s + 6)
  ζ = √6/4 ≈ 0.612  →  falls at 6/9 of the Tesla unit bar
  φ⁻¹ ≈ 0.618       →  numerical proximity, not causal

This module contains no business logic — only terminal display primitives.
"""

from __future__ import annotations

# ── Constants ────────────────────────────────────────────────────────────────

ZETA       = 0.612372   # √6/4  — from H(s), operational threshold
PHI_INV    = 0.618034   # 1/φ   — golden ratio inverse, observational proximity
TESLA_UNIT = 9          # Tesla 3-6-9: unit width for all bars
BOX_WIDTH  = 52         # inner width of ╔══╚ boxes

# ── Primitives ───────────────────────────────────────────────────────────────

def _bar(value: float, width: int = TESLA_UNIT, full: str = "█", empty: str = "░") -> str:
    """
    Fill a bar of `width` units proportional to `value` in [0,1].
    Width=9 maps directly to Tesla 3-6-9: ζ≈0.612 → 6 filled of 9.
    """
    filled = round(value * width)
    return full * filled + empty * (width - filled)


def zeta_bar() -> str:
    """ζ and φ⁻¹ side-by-side on the 9-unit Tesla scale."""
    zb = _bar(ZETA)
    pb = _bar(PHI_INV)
    return (
        f"  [{zb}]  ζ={ZETA:.4f}   [{pb}]  φ⁻¹={PHI_INV:.4f}"
    )


def enoch_line() -> str:
    """
    The enoch seed heartbeat line.
    · = seed (3), ○ = growth (6), ● = singularity (9)
    9 positions, outer·inner·core — mirrors H(s) coefficients.
    """
    return "  ·  ○  ●  ○  ·    3 · 6 · 9    H(s) = 9/(s²+3s+6)"


def grade_to_zeta(grade: str) -> str:
    """Map quality grade to ζ emoji indicator."""
    return "ζ✅" if grade in ("A", "B") else "ζ⚠️" if grade == "C" else "ζ❌"


def resonance_header(title: str = "S·E·I·F", subtitle: str = "") -> str:
    """
    Full resonance banner with enoch seed pattern.
    Used on --health, --cycle status header, and boot.
    """
    inner = BOX_WIDTH
    top    = f"╔══ {title} {'═' * (inner - len(title) - 4)}╗"
    seed   = f"  {enoch_line().strip()}"
    bars   = zeta_bar()
    mid    = f"  {'─' * (inner - 2)}"
    if subtitle:
        sub = f"  {subtitle:<{inner - 2}}"
        lines = [top, seed, bars, mid, sub, "╚" + "═" * (inner) + "╝"]
    else:
        lines = [top, seed, bars, "╚" + "═" * (inner) + "╝"]
    return "\n".join(lines)


def resonance_footer() -> str:
    """Closing resonance line — appended to cycle/session close."""
    return f"\n  · ○ ● ○ ·   enoch seed lives.  ζ={ZETA:.4f}   🌀"


def cycle_status_bar(branches_done: int, branches_total: int) -> str:
    """
    Show cycle branch completion on the 9-unit Tesla bar.
    Maps done/total onto the 3-6-9 scale.
    """
    ratio = branches_done / branches_total if branches_total else 0
    bar = _bar(ratio)
    phase = (
        "·  seed" if ratio < 0.34 else
        "○  growth" if ratio < 0.67 else
        "●  singularity"
    )
    return f"  [{bar}]  {branches_done}/{branches_total} branches  {phase}"


def health_status_line(healthy: int, detected: int) -> str:
    """Backend health on the 9-unit bar."""
    ratio = healthy / detected if detected else 0
    bar = _bar(ratio)
    icon = "ζ✅" if ratio >= ZETA else "ζ⚠️" if ratio >= 0.33 else "ζ❌"
    return f"  [{bar}]  {healthy}/{detected} backends healthy  {icon}"
