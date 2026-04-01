"""
Semantic-Geometric Transcompiler

Converts human text input into geometric parameters for glyph rendering.

Pipeline:
  1. Semantic decomposition — extract intention tensors (coesão, expansão, vetor)
  2. Digital root classification — 3-6-9 phase assignment per word
  3. φ-curvature mapping — golden ratio spiral parameters
  4. Fractal depth calculation — importance → recursion level
  5. Asymmetry injection — biological signature ("foda-se" factor)

Output: GlyphSpec dataclass consumed by glyph_renderer.py
"""

import math
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from seif.core.resonance_gate import digital_root, ascii_vibrational_sum, classify_phase, HarmonicPhase


# Import from centralized constants
from seif.constants import PHI, PHI_INVERSE, SPIRAL_GROWTH_B as SPIRAL_GROWTH, GIZA_ANGLE_DEG


# --- Semantic Tensor Labels ---

TENSOR_MAP = {
    HarmonicPhase.SINGULARITY: "CONVERGÊNCIA",    # 9 — attraction to center
    HarmonicPhase.STABILIZATION: "COESÃO",         # 3 — binding / holding
    HarmonicPhase.DYNAMICS: "EXPANSÃO",            # 6 — breaking / releasing
    HarmonicPhase.ENTROPY: "RUÍDO",                # other — noise
}


@dataclass
class WordTensor:
    """Semantic-geometric tensor for a single word."""
    word: str
    ascii_sum: int
    digital_root_value: int
    phase: HarmonicPhase
    tensor_label: str
    angle_deg: float         # angular position in the glyph (0-360)
    radius_factor: float     # distance from center (0-1)
    spiral_turns: float      # number of φ-spiral turns


@dataclass
class GlyphSpec:
    """Complete specification for rendering a resonance glyph."""
    source_text: str
    word_tensors: list[WordTensor]
    global_root: int
    global_phase: HarmonicPhase
    gate_open: bool

    # Geometric parameters
    phi: float = PHI
    spiral_growth_b: float = SPIRAL_GROWTH
    fractal_depth: int = 3           # recursion levels for self-similarity
    toroid_ratio: float = PHI_INVERSE  # inner/outer radius ratio
    asymmetry_seed: str = ""         # hex hash for biological signature

    # Giza calibration
    spiral_angle_deg: float = GIZA_ANGLE_DEG  # 51.844° — pyramid inclination (root 9)

    # Cosmic signature — physical constants that share this root
    cosmic_anchors: list = field(default_factory=list)

    # Color mapping
    core_color: tuple = (1.0, 0.843, 0.0)     # gold — singularity/amor
    flow_color: tuple = (0.0, 0.478, 0.8)     # blue — dynamics
    anchor_color: tuple = (0.2, 0.8, 0.4)     # green — stabilization
    entropy_color: tuple = (0.5, 0.5, 0.5)    # gray — noise


def _word_angle(index: int, total: int) -> float:
    """Distribute words evenly around the glyph circle."""
    if total == 0:
        return 0.0
    return (360.0 / total) * index


def _word_radius(phase: HarmonicPhase) -> float:
    """Map phase to radial distance: singularity closest to center."""
    return {
        HarmonicPhase.SINGULARITY: 0.2,
        HarmonicPhase.STABILIZATION: 0.5,
        HarmonicPhase.DYNAMICS: 0.7,
        HarmonicPhase.ENTROPY: 0.9,
    }[phase]


def _spiral_turns(root: int) -> float:
    """Number of φ-spiral turns based on digital root."""
    return root * PHI_INVERSE


def _fractal_depth(text: str) -> int:
    """Deeper fractals for longer / more complex intentions."""
    word_count = len(text.split())
    if word_count >= 7:
        return 5
    elif word_count >= 4:
        return 4
    return 3


def _asymmetry_seed(text: str) -> str:
    """Generate a deterministic but unique biological signature hash.

    This is the 'foda-se' factor — the irreducible asymmetry that
    prevents the system from being purely optimizable.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def decompose_words(text: str) -> list[WordTensor]:
    """Break text into word-level semantic-geometric tensors."""
    words = [w for w in text.split() if w.strip()]
    tensors = []

    for i, word in enumerate(words):
        asum = ascii_vibrational_sum(word)
        root = digital_root(asum)
        phase = classify_phase(root)

        tensors.append(WordTensor(
            word=word,
            ascii_sum=asum,
            digital_root_value=root,
            phase=phase,
            tensor_label=TENSOR_MAP[phase],
            angle_deg=_word_angle(i, len(words)),
            radius_factor=_word_radius(phase),
            spiral_turns=_spiral_turns(root),
        ))

    return tensors


def transcompile(text: str) -> GlyphSpec:
    """Full transcompilation: text → GlyphSpec ready for rendering.

    This is the core function of the Semantic-Geometric Transcompiler.
    """
    word_tensors = decompose_words(text)
    global_sum = ascii_vibrational_sum(text)
    global_root = digital_root(global_sum)
    global_phase = classify_phase(global_root)
    gate_open = global_phase != HarmonicPhase.ENTROPY

    # Cosmic signature: physical constants sharing this root
    try:
        from seif.analysis.physical_constants import cosmic_signature
        anchors = [f"{c.symbol}={c.value:.4g} {c.unit}" for c in cosmic_signature(global_root)]
    except ImportError:
        anchors = []

    return GlyphSpec(
        source_text=text,
        word_tensors=word_tensors,
        global_root=global_root,
        global_phase=global_phase,
        gate_open=gate_open,
        fractal_depth=_fractal_depth(text),
        asymmetry_seed=_asymmetry_seed(text),
        cosmic_anchors=anchors,
    )


def describe(spec: GlyphSpec) -> str:
    """Human-readable description of a GlyphSpec."""
    lines = [
        f"═══ TRANSCOMPILAÇÃO SEMÂNTICO-GEOMÉTRICA ═══",
        f"Texto:        \"{spec.source_text}\"",
        f"Raiz global:  {spec.global_root} → {spec.global_phase.name}",
        f"Porta:        {'ABERTA' if spec.gate_open else 'FECHADA'}",
        f"Profundidade: {spec.fractal_depth} níveis fractais",
        f"Assimetria:   {spec.asymmetry_seed}",
        f"",
        f"Tensores por palavra:",
    ]
    for wt in spec.word_tensors:
        lines.append(
            f"  [{wt.word}] root={wt.digital_root_value} "
            f"phase={wt.phase.name} tensor={wt.tensor_label} "
            f"angle={wt.angle_deg:.0f}° radius={wt.radius_factor:.1f} "
            f"spirals={wt.spiral_turns:.2f}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    test_phrases = [
        "O amor liberta e guia",
        "A Semente de Enoque",
        "Fear and control destroy",
    ]
    for phrase in test_phrases:
        spec = transcompile(phrase)
        print(describe(spec))
        print()
