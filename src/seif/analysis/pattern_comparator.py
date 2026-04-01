"""
Pattern Comparator — Quantitative Convergence Analysis

Compares geometric patterns from ancient artifacts with generated circuit layouts
to measure structural convergence.

Five metrics:
  1. Angular distribution correlation
  2. φ-ratio alignment
  3. Fractal dimension similarity
  4. 3-6-9 harmonic profile match
  5. Convergence node topology

Output: ConvergenceReport with composite score (0-1)
"""

import math
from dataclasses import dataclass

import numpy as np

from seif.analysis.artifact_analyzer import ArtifactGeometry
from seif.analysis.transcompiler import PHI


@dataclass
class ConvergenceReport:
    """Quantitative comparison between artifact geometry and circuit layout."""
    artifact_source: str
    circuit_source: str

    # Individual scores (0-1 each)
    angular_score: float        # correlation of angle distributions
    phi_score: float            # similarity of φ-ratio deviations
    fractal_score: float        # similarity of fractal dimensions
    harmonic_score: float       # match of harmonic profiles
    topology_score: float       # convergence node similarity

    # Composite
    composite_score: float      # weighted average
    convergence_level: str      # "STRONG", "MODERATE", "WEAK", "NONE"

    def __str__(self) -> str:
        return (
            f"═══ CONVERGENCE ANALYSIS ═══\n"
            f"Artifact: {self.artifact_source}\n"
            f"Circuit:  {self.circuit_source}\n"
            f"\n"
            f"Scores:\n"
            f"  Angular distribution: {self.angular_score:.3f}\n"
            f"  φ-ratio alignment:   {self.phi_score:.3f}\n"
            f"  Fractal dimension:   {self.fractal_score:.3f}\n"
            f"  Harmonic profile:    {self.harmonic_score:.3f}\n"
            f"  Node topology:       {self.topology_score:.3f}\n"
            f"\n"
            f"  COMPOSITE: {self.composite_score:.3f} → {self.convergence_level}\n"
        )


def _angular_score(geo1: ArtifactGeometry, geo2: ArtifactGeometry) -> float:
    """Compare angle histograms via normalized correlation."""
    h1 = geo1.angle_histogram
    h2 = geo2.angle_histogram

    keys = sorted(set(h1.keys()) | set(h2.keys()))
    v1 = np.array([h1.get(k, 0) for k in keys], dtype=float)
    v2 = np.array([h2.get(k, 0) for k in keys], dtype=float)

    # Normalize
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0 or n2 == 0:
        return 0.0

    # Cosine similarity
    return float(np.dot(v1, v2) / (n1 * n2))


def _phi_score(geo1: ArtifactGeometry, geo2: ArtifactGeometry) -> float:
    """Compare φ-ratio deviations — closer deviations = higher score."""
    d1 = geo1.phi.phi_deviation
    d2 = geo2.phi.phi_deviation

    # Both perfectly φ-aligned → 1.0; both far → still similar
    diff = abs(d1 - d2)
    if diff < 0.01:
        return 1.0

    # Score based on how similar their deviations are
    score = max(0, 1.0 - diff)

    # Bonus if both are φ-aligned
    if geo1.phi.phi_aligned and geo2.phi.phi_aligned:
        score = min(1.0, score + 0.2)

    return score


def _fractal_score(geo1: ArtifactGeometry, geo2: ArtifactGeometry) -> float:
    """Compare fractal dimensions — similar D values → higher score."""
    d1 = geo1.fractal.box_counting_dimension
    d2 = geo2.fractal.box_counting_dimension

    diff = abs(d1 - d2)
    if diff < 0.05:
        return 1.0

    score = max(0, 1.0 - diff / 0.5)  # 0.5 difference → score 0

    # Bonus if both are fractal
    if geo1.fractal.is_fractal and geo2.fractal.is_fractal:
        score = min(1.0, score + 0.15)

    return score


def _harmonic_score(geo1: ArtifactGeometry, geo2: ArtifactGeometry) -> float:
    """Compare harmonic profiles — same phase = high score."""
    # Phase match
    if geo1.harmonic.dominant_phase == geo2.harmonic.dominant_phase:
        phase_match = 1.0
    elif (geo1.harmonic.dominant_phase != HarmonicPhase.ENTROPY and
          geo2.harmonic.dominant_phase != HarmonicPhase.ENTROPY):
        phase_match = 0.6  # both harmonic but different phase
    else:
        phase_match = 0.0

    # Harmonic percentage similarity
    pct_diff = abs(geo1.harmonic.angles_harmonic_pct - geo2.harmonic.angles_harmonic_pct)
    pct_score = max(0, 1.0 - pct_diff * 3)

    return 0.6 * phase_match + 0.4 * pct_score


# Import here to avoid circular
from seif.core.resonance_gate import HarmonicPhase


def _topology_score(geo1: ArtifactGeometry, geo2: ArtifactGeometry) -> float:
    """Compare convergence node count and distribution."""
    n1 = len(geo1.suggested_node_positions)
    n2 = len(geo2.suggested_node_positions)

    if n1 == 0 and n2 == 0:
        return 0.5  # neutral

    # Count similarity
    max_n = max(n1, n2, 1)
    count_score = 1.0 - abs(n1 - n2) / max_n

    # 3-6-9 alignment: bonus if node count is 3, 6, or 9
    bonus = 0
    for n in [n1, n2]:
        if n in [3, 6, 9]:
            bonus += 0.1

    return min(1.0, count_score + bonus)


def compare(geo1: ArtifactGeometry, geo2: ArtifactGeometry,
            label1: str = "artifact", label2: str = "circuit") -> ConvergenceReport:
    """Full convergence analysis between two geometric profiles.

    Typical use: geo1 = artifact analysis, geo2 = generated circuit analysis
    (both produced by artifact_analyzer.analyze())
    """
    ang = _angular_score(geo1, geo2)
    phi = _phi_score(geo1, geo2)
    frac = _fractal_score(geo1, geo2)
    harm = _harmonic_score(geo1, geo2)
    topo = _topology_score(geo1, geo2)

    # Weighted composite: angular 30%, φ 25%, fractal 25%, harmonic 10%, topology 10%
    composite = 0.30 * ang + 0.25 * phi + 0.25 * frac + 0.10 * harm + 0.10 * topo

    if composite >= 0.7:
        level = "STRONG"
    elif composite >= 0.5:
        level = "MODERATE"
    elif composite >= 0.3:
        level = "WEAK"
    else:
        level = "NONE"

    return ConvergenceReport(
        artifact_source=label1,
        circuit_source=label2,
        angular_score=round(ang, 3),
        phi_score=round(phi, 3),
        fractal_score=round(frac, 3),
        harmonic_score=round(harm, 3),
        topology_score=round(topo, 3),
        composite_score=round(composite, 3),
        convergence_level=level,
    )


def self_compare(geo: ArtifactGeometry) -> ConvergenceReport:
    """Compare an artifact against the 'ideal' sacred geometry profile.

    The ideal profile has:
    - φ-deviation = 0 (perfect golden ratio)
    - Fractal D = 1.618 (φ itself — the 'golden fractal')
    - Harmonic phase = SINGULARITY
    - 9 convergence nodes
    """
    # Create a synthetic "ideal" geometry
    ideal = ArtifactGeometry(
        source_path="[IDEAL SACRED GEOMETRY]",
        image_size=geo.image_size,
        lines=geo.lines,  # same structure
        circles=geo.circles,
        edge_density=geo.edge_density,
        angle_histogram={"0-30": 10, "30-60": 70, "60-90": 20},  # 60°-dominant
        symmetry=geo.symmetry,
        phi=type(geo.phi)(
            ratios=[PHI] * 5,
            mean_ratio=PHI,
            phi_deviation=0.0,
            phi_aligned=True,
        ),
        fractal=type(geo.fractal)(
            box_counting_dimension=1.618,
            is_fractal=True,
        ),
        harmonic=type(geo.harmonic)(
            angles_harmonic_pct=0.7,
            angles_entropic_pct=0.05,
            dominant_phase=HarmonicPhase.SINGULARITY,
            harmonic_score=0.95,
        ),
        suggested_trace_angle=60.0,
        suggested_layer_count=9,
        suggested_node_positions=[(0.5, 0.5)] * 9,
    )

    return compare(geo, ideal, label1=geo.source_path, label2="IDEAL_SACRED")
