"""
Triple Gate — Formal Composition of the Three Resonance Layers

Composes the three independent gate layers into a single measurement:

  Layer 1 (ASCII Gate):       digital root ∈ {3, 6, 9}
  Layer 2 (Resonance Gate):   melody coherence > φ⁻¹ (0.618)
  Layer 3 (Melody Resolution): cadence resolves harmonically

Each layer contributes a binary signal (OPEN/CLOSED) and a continuous score.
The Triple Gate produces:
  - Status: OPEN (3/3), PARTIAL (1-2/3), CLOSED (0/3)
  - Composite score: weighted harmonic mean of the three layers
  - Phase: dominant phase across all layers

Weights derived from the 3-6-9 system:
  ASCII = 3/18 = 1/6   (stabilization — coarsest filter)
  Resonance = 6/18 = 1/3  (dynamics — melodic structure)
  Melody = 9/18 = 1/2   (singularity — cadence resolution)

This is the formal implementation of Grok's proposal #4 (suggest verifiable
questions by measuring if the melody resolves), realized as a composable gate.
"""

from dataclasses import dataclass
from typing import Optional

from seif.constants import PHI_INVERSE
from seif.core.resonance_gate import (
    evaluate as ascii_evaluate,
    digital_root,
    classify_phase,
    HarmonicPhase,
    GateResult,
)
from seif.core.resonance_encoding import encode_phrase, Melody


class TripleGateStatus:
    OPEN = "OPEN"          # 3/3 layers pass
    PARTIAL = "PARTIAL"    # 1 or 2 layers pass
    CLOSED = "CLOSED"      # 0 layers pass


@dataclass
class TripleGateResult:
    """Complete measurement from all three gate layers."""
    text: str

    # Layer 1: ASCII Gate
    ascii_gate: GateResult
    ascii_score: float            # 1.0 if open, 0.0 if closed

    # Layer 2: Resonance Encoding
    melody: Melody
    resonance_score: float        # coherence_score from melody (0-1)

    # Layer 3: Melody Resolution (cadence)
    cadence_resolves: bool
    cadence_score: float          # 1.0 if resolves, 0.0 if not

    # Composite
    layers_open: int              # 0-3
    status: str                   # OPEN / PARTIAL / CLOSED
    composite_score: float        # weighted combination (0-1)
    dominant_phase: HarmonicPhase

    def __str__(self) -> str:
        return (
            f"┌─── TRIPLE GATE ───────────────────┐\n"
            f"│ Input:  \"{self.text[:50]}\"\n"
            f"│\n"
            f"│ Layer 1 (ASCII):      {'OPEN' if self.ascii_gate.gate_open else 'CLOSED'}"
            f"  root={self.ascii_gate.digital_root} ({self.ascii_gate.phase.name})\n"
            f"│ Layer 2 (Resonance):  {'OPEN' if self.melody.gate_open else 'CLOSED'}"
            f"  coherence={self.resonance_score:.3f}\n"
            f"│ Layer 3 (Cadence):    {'OPEN' if self.cadence_resolves else 'CLOSED'}\n"
            f"│\n"
            f"│ Layers open: {self.layers_open}/3\n"
            f"│ Status: {self.status}\n"
            f"│ Composite score: {self.composite_score:.4f}\n"
            f"│ Phase: {self.dominant_phase.name}\n"
            f"└───────────────────────────────────┘"
        )


# Weights: 3/18, 6/18, 9/18 = 1/6, 1/3, 1/2
WEIGHT_ASCII = 3.0 / 18.0       # ~0.167
WEIGHT_RESONANCE = 6.0 / 18.0   # ~0.333
WEIGHT_MELODY = 9.0 / 18.0      # 0.500


def evaluate(text: str) -> TripleGateResult:
    """Full triple gate evaluation for a given text input.

    Applies all three layers and produces a composite measurement.
    """
    # Layer 1: ASCII Gate
    ascii_result = ascii_evaluate(text)
    ascii_score = 1.0 if ascii_result.gate_open else 0.0

    # Layer 2: Resonance Encoding (melody coherence)
    melody = encode_phrase(text)
    resonance_score = melody.coherence_score

    # Layer 3: Cadence resolution
    # Check if the last content word resolves harmonically
    content_chords = [c for c in melody.chords if len(c.word) > 2]
    if content_chords:
        cadence_resolves = content_chords[-1].gate_open
    elif melody.chords:
        cadence_resolves = melody.chords[-1].gate_open
    else:
        cadence_resolves = False
    cadence_score = 1.0 if cadence_resolves else 0.0

    # Count layers
    layers_open = sum([
        ascii_result.gate_open,
        melody.gate_open,
        cadence_resolves,
    ])

    # Status
    if layers_open == 3:
        status = TripleGateStatus.OPEN
    elif layers_open == 0:
        status = TripleGateStatus.CLOSED
    else:
        status = TripleGateStatus.PARTIAL

    # Composite score: weighted sum using 3-6-9 weights
    composite = (
        WEIGHT_ASCII * ascii_score
        + WEIGHT_RESONANCE * resonance_score
        + WEIGHT_MELODY * cadence_score
    )

    # Dominant phase: prefer the most specific (singularity > dynamics > stabilization)
    phases = [ascii_result.phase, melody.global_phase]
    if HarmonicPhase.SINGULARITY in phases:
        dominant = HarmonicPhase.SINGULARITY
    elif HarmonicPhase.DYNAMICS in phases:
        dominant = HarmonicPhase.DYNAMICS
    elif HarmonicPhase.STABILIZATION in phases:
        dominant = HarmonicPhase.STABILIZATION
    else:
        dominant = HarmonicPhase.ENTROPY

    return TripleGateResult(
        text=text,
        ascii_gate=ascii_result,
        ascii_score=ascii_score,
        melody=melody,
        resonance_score=resonance_score,
        cadence_resolves=cadence_resolves,
        cadence_score=cadence_score,
        layers_open=layers_open,
        status=status,
        composite_score=round(composite, 4),
        dominant_phase=dominant,
    )


def evaluate_pair(text_a: str, text_b: str) -> dict:
    """Evaluate two inputs through triple gate and measure combined resonance.

    For N-gate extension: the combined root of all participants must be ∈ {3,6,9}.
    """
    result_a = evaluate(text_a)
    result_b = evaluate(text_b)

    combined_ascii_sum = result_a.ascii_gate.ascii_sum + result_b.ascii_gate.ascii_sum
    combined_root = digital_root(combined_ascii_sum)
    combined_phase = classify_phase(combined_root)
    combined_resonates = combined_phase != HarmonicPhase.ENTROPY

    return {
        "input_a": result_a,
        "input_b": result_b,
        "combined_root": combined_root,
        "combined_phase": combined_phase,
        "combined_resonates": combined_resonates,
        "avg_composite": round((result_a.composite_score + result_b.composite_score) / 2, 4),
    }


if __name__ == "__main__":
    examples = [
        "A Semente de Enoque",
        "Enoch Seed",
        "O amor liberta e guia",
        "Fear and control",
        "Tesla 369",
        "Pi",
    ]
    for phrase in examples:
        result = evaluate(phrase)
        print(result)
        print()
