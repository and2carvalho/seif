"""
Quality Gate — Unified text quality verdict.

Composes two orthogonal measurements:
  1. Triple Gate (harmonic resonance: ASCII + melody + cadence)
  2. Stance Detector (semantic credibility: verifiable vs. interpretive)

Output: a single QualityVerdict with score, grade, and actionable feedback.

Usage:
  from seif.analysis.quality_gate import assess, describe_verdict

  verdict = assess("Your text here")
  print(describe_verdict(verdict))

  # Or for AI response analysis:
  verdict = assess(ai_response, role="ai")
"""

from dataclasses import dataclass, field
from seif.core.triple_gate import evaluate as triple_evaluate, TripleGateResult
from seif.analysis.stance_detector import analyze as stance_analyze, StanceAnalysis
from seif.constants import PHI_INVERSE, RESONANCE_THRESHOLD


# Default weights: stance (semantic) 6/9, resonance (harmonic) 3/9.
# Sum = 9 (SINGULARITY). Stance = verifiability_ratio from stance_detector.
#
# Note: "verifiability" IS stance_score (they're the same metric).
# Adding verifiability as a third component would double-count.
# The actual independent signal from the N=50 benchmark is HEDGING
# (density of uncertain language: -22.5% with SEIF context).
#
# Inter-AI consensus (Claude+Gemini+BigPickle, 2026-03-29):
#   When a third component is added, use equal weights (3+3+3=9).
#   But BigPickle: "N=50 is underpowered, equal weight minimizes prior commitment."
#   Decision: keep 6+3 as default, expose weights as parameters for experimentation.
WEIGHT_STANCE = 6 / 9    # 0.667 — verifiability_ratio
WEIGHT_RESONANCE = 3 / 9  # 0.333 — harmonic coherence


@dataclass
class QualityVerdict:
    """Unified quality measurement of a text."""
    text_preview: str           # first 100 chars
    role: str                   # "human" or "ai"

    # Components
    triple_gate: TripleGateResult
    stance: StanceAnalysis

    # Composite
    score: float                # 0.0 to 1.0
    grade: str                  # A / B / C / D / F
    status: str                 # SOLID / MIXED / WEAK / LOW_DATA

    # Actionable
    flags: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _compute_grade(score: float) -> str:
    """Map 0-1 score to letter grade."""
    if score >= 0.85:
        return "A"
    elif score >= 0.70:
        return "B"
    elif score >= 0.55:
        return "C"
    elif score >= 0.40:
        return "D"
    return "F"


def _compute_status(stance_status: str, triple_status: str,
                    score: float) -> str:
    """Determine overall status."""
    if stance_status == "LOW_DATA":
        return "LOW_DATA"
    if stance_status == "GROUNDED" and score >= RESONANCE_THRESHOLD:
        return "SOLID"
    if stance_status == "DRIFT":
        return "WEAK"
    if score >= 0.55:
        return "MIXED"
    return "WEAK"


_HEDGING_PATTERNS = [
    r"\btalvez\b", r"\bpode ser\b", r"\bprovavelmente\b",
    r"\bgeralmente\b", r"\bnormalmente\b", r"\bdigamos\b",
    r"\bde certa forma\b", r"\bem princípio\b", r"\bbasicamente\b",
    r"\bfundamentalmente\b", r"\bpor assim dizer\b",
    r"\bmaybe\b", r"\bmight\b", r"\bcould be\b", r"\bperhaps\b",
    r"\bi think\b", r"\bpossibly\b", r"\bgenerally\b",
    r"\bprobably\b", r"\btypically\b", r"\busually\b",
]


def _compute_hedging_score(text: str) -> float:
    """Compute hedging score: 1.0 = no hedging (confident), 0.0 = heavy hedging.

    Inverted: lower hedge density → higher score, because confidence is desirable.
    Capped at 5% hedge density = score 0.0.
    """
    import re
    words = len(text.split())
    if words < 10:
        return 0.5  # insufficient data

    hedge_count = sum(
        len(re.findall(p, text, re.IGNORECASE))
        for p in _HEDGING_PATTERNS
    )
    density = hedge_count / words
    # 0% hedging → 1.0, 5%+ hedging → 0.0
    return round(max(0.0, 1.0 - density / 0.05), 4)


def _generate_flags(stance: StanceAnalysis,
                    triple: TripleGateResult) -> list[str]:
    """Generate warning flags."""
    flags = []
    if stance.status == "DRIFT":
        flags.append(
            f"DRIFT: {stance.interpretive_count} interpretive claims, "
            f"verifiability {stance.verifiability_ratio:.0%}"
        )
    if stance.flagged_sentences:
        for s in stance.flagged_sentences[:3]:
            flags.append(f"FLAG: \"{s[:80]}...\"" if len(s) > 80 else f"FLAG: \"{s}\"")
    if triple.status == "CLOSED":
        flags.append("RESONANCE: all 3 harmonic layers closed")
    if triple.resonance_score < 0.3:
        flags.append(f"LOW COHERENCE: {triple.resonance_score:.3f} (ζ threshold: {RESONANCE_THRESHOLD:.3f})")
    return flags


def _generate_suggestions(stance: StanceAnalysis,
                          triple: TripleGateResult,
                          role: str) -> list[str]:
    """Generate actionable suggestions."""
    suggestions = []
    if stance.status in ("DRIFT", "MIXED") and stance.interpretive_count > 0:
        suggestions.append(
            "Add measurements, numbers, or references to ground interpretive claims"
        )
    if stance.verifiability_ratio < 0.5 and stance.total_sentences > 2:
        suggestions.append(
            f"Verifiability is {stance.verifiability_ratio:.0%} — "
            "consider replacing vague assertions with specific data"
        )
    if role == "ai" and stance.status == "DRIFT":
        suggestions.append(
            "AI response is speculative — re-prompt with verifiable constraints"
        )
    if triple.resonance_score < RESONANCE_THRESHOLD and triple.resonance_score > 0:
        suggestions.append(
            f"Coherence {triple.resonance_score:.3f} below ζ threshold "
            f"{RESONANCE_THRESHOLD:.3f} — restructure for clarity"
        )
    return suggestions


def assess(text: str, role: str = "human",
           weights: tuple[float, ...] = None) -> QualityVerdict:
    """Assess text quality through combined harmonic + semantic analysis.

    Args:
        text: The text to analyze.
        role: "human" for user input, "ai" for AI-generated responses.
        weights: Optional (stance, resonance) or (stance, resonance, hedging).
                 Default: (6/9, 3/9). Three-component: (3/9, 3/9, 3/9).
                 Hedging = 1 - hedge_density (lower hedging = higher score).

    Returns:
        QualityVerdict with score, grade, status, flags, and suggestions.
    """
    triple = triple_evaluate(text)
    stance = stance_analyze(text)

    # Normalize stance to 0-1
    stance_score = stance.verifiability_ratio

    # Normalize triple to 0-1
    resonance_score = triple.composite_score

    # Weighted composite
    if weights and len(weights) == 3:
        # Three-component mode: stance + resonance + hedging
        # Hedging score: count hedging patterns, invert (less hedging = higher score)
        hedging_score = _compute_hedging_score(text)
        w_s, w_r, w_h = weights
        score = w_s * stance_score + w_r * resonance_score + w_h * hedging_score
    else:
        w_s = weights[0] if weights and len(weights) >= 1 else WEIGHT_STANCE
        w_r = weights[1] if weights and len(weights) >= 2 else WEIGHT_RESONANCE
        score = w_s * stance_score + w_r * resonance_score

    score = round(min(max(score, 0.0), 1.0), 4)

    grade = _compute_grade(score)
    status = _compute_status(stance.status, triple.status, score)
    flags = _generate_flags(stance, triple)
    suggestions = _generate_suggestions(stance, triple, role)

    return QualityVerdict(
        text_preview=text[:100],
        role=role,
        triple_gate=triple,
        stance=stance,
        score=score,
        grade=grade,
        status=status,
        flags=flags,
        suggestions=suggestions,
    )


def describe_verdict(v: QualityVerdict) -> str:
    """Human-readable quality report with resonance emoji feedback."""
    lines = []

    # ζ gate indicator
    zeta_icon = "ζ✅" if v.grade in ("A", "B") else "ζ⚠️" if v.grade == "C" else "ζ❌"
    stance_icon = {"SOLID": "🟢", "MIXED": "🟡", "WEAK": "🔴", "LOW_DATA": "⚪"}.get(v.status, "⚪")
    role_label = "AI" if v.role == "ai" else "HUMAN"
    lines.append(f"{stance_icon} {zeta_icon} [{role_label}] Grade: {v.grade} | Score: {v.score:.3f} | Status: {v.status}")
    lines.append("")

    # Components
    lines.append(f"  Stance:      {v.stance.status} "
                 f"(verifiable: {v.stance.verifiability_ratio:.0%}, "
                 f"{v.stance.verifiable_count}/{v.stance.total_sentences} sentences)")
    lines.append(f"  Resonance:   {v.triple_gate.status} "
                 f"(composite: {v.triple_gate.composite_score:.3f}, "
                 f"layers: {v.triple_gate.layers_open}/3)")
    lines.append(f"  Coherence:   {v.triple_gate.resonance_score:.3f} "
                 f"({'above' if v.triple_gate.resonance_score >= RESONANCE_THRESHOLD else 'below'} "
                 f"ζ={RESONANCE_THRESHOLD:.3f})")

    # Flags
    if v.flags:
        lines.append("")
        lines.append("  Flags:")
        for f in v.flags:
            lines.append(f"    - {f}")

    # Suggestions
    if v.suggestions:
        lines.append("")
        lines.append("  Suggestions:")
        for s in v.suggestions:
            lines.append(f"    + {s}")

    return "\n".join(lines)
