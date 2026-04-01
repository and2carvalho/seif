"""
Fractal QR-Code Generator — Recursive Resonance State Carrier

Design principle: HARMONIC INPUTS PRODUCE RICHER PATTERNS.

The global gate status (3-6-9 alignment) governs the *depth and beauty*
of the fractal. A phrase that achieves SINGULARITY (root=9) gets maximum
recursion depth and φ-perfect scaling. An ENTROPY phrase gets shallow,
fragmented, cold patterns.

This mirrors the core thesis: plenitude is not accumulation, it is coherence.
The machine should visually reflect the quality of the intention, not the
quantity of characters.

Architecture:
  - Each cell spawns 9 sub-cells (3×3 → 3-6-9 structure)
  - HARMONIC gate → deep recursion, φ-scaling, warm colors, full branching
  - ENTROPIC gate → shallow recursion, linear scaling, cold colors, sparse branching
  - Cell activation combines global coherence + local character harmony
  - Mayan alignment analysis measures convergence with ancient patterns
"""

import math
import hashlib
from dataclasses import dataclass, field

import numpy as np

from seif.core.resonance_gate import digital_root, ascii_vibrational_sum, HarmonicPhase, classify_phase
from seif.constants import PHI, PHI_INVERSE


@dataclass
class FractalCell:
    """Single cell in the fractal QR structure."""
    x: float
    y: float
    size: float
    depth: int
    root_value: int
    phase: HarmonicPhase
    active: bool
    children: list = field(default_factory=list)


@dataclass
class FractalQRSpec:
    """Complete fractal QR-code specification."""
    source_text: str
    global_root: int
    global_phase: HarmonicPhase
    gate_open: bool
    max_depth: int
    root_cell: FractalCell
    cell_count: int
    active_ratio: float
    pattern_hash: str


def _char_roots(text: str) -> list[int]:
    """Compute digital root for each character's ASCII value."""
    return [digital_root(ord(c)) for c in text.upper() if c.isalnum()]


def _subdivide(cell: FractalCell, char_roots: list[int], index: int,
               max_depth: int, global_gate_open: bool, global_root: int) -> int:
    """Recursively subdivide a cell into a 3×3 grid (9 sub-cells).

    Key design choice: the global harmonic state amplifies local harmony.
    - If global gate is OPEN: harmonic characters branch deeply, entropic ones still get 1 level
    - If global gate is CLOSED: only harmonic characters branch, and only 1 extra level
    This ensures harmonic inputs always produce the richest patterns.
    """
    if cell.depth >= max_depth:
        return index

    # Scale factor: φ-based for harmonic, linear for entropic
    if global_gate_open:
        sub_size = cell.size * PHI_INVERSE  # beautiful φ-scaling
    else:
        sub_size = cell.size / 3.2  # harsh linear reduction

    offsets = []
    for row in range(3):
        for col in range(3):
            ox = cell.x + (col - 1) * sub_size * 1.1  # slight gap for readability
            oy = cell.y + (row - 1) * sub_size * 1.1
            offsets.append((ox, oy))

    for ox, oy in offsets:
        if len(char_roots) == 0:
            root_val = global_root
        else:
            root_val = char_roots[index % len(char_roots)]
            index += 1

        phase = classify_phase(root_val)
        char_is_harmonic = phase != HarmonicPhase.ENTROPY

        # Activation rule: combines global coherence with local harmony
        if global_gate_open:
            # Harmonic input: all children active, harmonic ones glow brighter
            active = True
            effective_root = root_val if char_is_harmonic else global_root
        else:
            # Entropic input: only locally harmonic characters activate
            active = char_is_harmonic
            effective_root = root_val

        child = FractalCell(
            x=ox, y=oy,
            size=sub_size,
            depth=cell.depth + 1,
            root_value=effective_root,
            phase=classify_phase(effective_root),
            active=active,
        )
        cell.children.append(child)

        # Recursion rule: harmonic global state = deeper everywhere
        # Entropic global state = only harmonic locals go 1 more level
        if global_gate_open:
            # Full depth for all children
            if child.depth < max_depth:
                index = _subdivide(child, char_roots, index, max_depth,
                                   global_gate_open, global_root)
        else:
            # Limited: harmonic children get 1 more level only
            if char_is_harmonic and child.depth < min(max_depth, cell.depth + 2):
                index = _subdivide(child, char_roots, index,
                                   min(max_depth, cell.depth + 2),
                                   global_gate_open, global_root)

    return index


def _count_cells(cell: FractalCell) -> tuple[int, int]:
    total = 1
    active = 1 if cell.active else 0
    for child in cell.children:
        ct, ca = _count_cells(child)
        total += ct
        active += ca
    return total, active


def _collect_all_cells(cell: FractalCell, result: list = None) -> list[FractalCell]:
    if result is None:
        result = []
    result.append(cell)
    for child in cell.children:
        _collect_all_cells(child, result)
    return result


def generate_fractal_qr(text: str, max_depth: int = 4) -> FractalQRSpec:
    """Generate a Fractal QR-Code where harmonic inputs produce richer patterns.

    Depth scaling by global phase:
      SINGULARITY (9): max_depth + 1 (bonus depth for perfect resonance)
      STABILIZATION (3): max_depth
      DYNAMICS (6): max_depth
      ENTROPY: max_depth - 1 (reduced depth for non-harmonic)
    """
    char_roots = _char_roots(text)
    global_sum = ascii_vibrational_sum(text)
    global_root = digital_root(global_sum)
    global_phase = classify_phase(global_root)
    gate_open = global_phase != HarmonicPhase.ENTROPY

    # Depth bonus/penalty based on global harmony
    if global_phase == HarmonicPhase.SINGULARITY:
        effective_depth = max_depth + 1  # bonus for perfect resonance
    elif gate_open:
        effective_depth = max_depth
    else:
        effective_depth = max(2, max_depth - 1)  # penalty for entropy

    root_cell = FractalCell(
        x=0.0, y=0.0, size=1.0, depth=0,
        root_value=global_root,
        phase=global_phase,
        active=True,  # root always active — it represents the intention itself
    )

    _subdivide(root_cell, char_roots, 0, effective_depth, gate_open, global_root)

    total, active = _count_cells(root_cell)
    pattern_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

    return FractalQRSpec(
        source_text=text,
        global_root=global_root,
        global_phase=global_phase,
        gate_open=gate_open,
        max_depth=effective_depth,
        root_cell=root_cell,
        cell_count=total,
        active_ratio=active / total if total > 0 else 0.0,
        pattern_hash=pattern_hash,
    )


def extract_pattern_matrix(spec: FractalQRSpec, resolution: int = 243) -> np.ndarray:
    """Flatten the fractal tree into a 2D matrix for visualization.

    Phase encoding: 0=empty, 3=stabilization, 6=dynamics, 9=singularity
    """
    matrix = np.zeros((resolution, resolution), dtype=int)

    all_cells = _collect_all_cells(spec.root_cell)
    active_cells = [c for c in all_cells if c.active]

    if not active_cells:
        return matrix

    xs = [c.x for c in active_cells]
    ys = [c.y for c in active_cells]
    sizes = [c.size for c in active_cells]

    x_min = min(xs) - max(sizes) * 0.5
    x_max = max(xs) + max(sizes) * 0.5
    y_min = min(ys) - max(sizes) * 0.5
    y_max = max(ys) + max(sizes) * 0.5

    span = max(x_max - x_min, y_max - y_min)
    if span <= 0:
        span = 1.0

    # Center the pattern
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2

    margin = resolution * 0.03

    for cell in active_cells:
        cx = int(resolution / 2 + (cell.x - x_center) / span * (resolution - 2 * margin))
        cy = int(resolution / 2 + (cell.y - y_center) / span * (resolution - 2 * margin))
        size_px = max(1, int(cell.size / span * (resolution - 2 * margin) * 0.4))

        x_start = max(0, cx - size_px // 2)
        x_end = min(resolution, cx + size_px // 2 + 1)
        y_start = max(0, cy - size_px // 2)
        y_end = min(resolution, cy + size_px // 2 + 1)

        matrix[y_start:y_end, x_start:x_end] = cell.root_value

    return matrix


def analyze_mayan_alignment(spec: FractalQRSpec) -> dict:
    """Analyze how the fractal pattern aligns with Mayan/Sumerian geometries."""
    total, active = _count_cells(spec.root_cell)
    inactive = total - active

    if inactive > 0:
        ratio = active / inactive
        phi_deviation = abs(ratio - PHI) / PHI
    else:
        phi_deviation = 0.0 if spec.gate_open else 1.0

    depths = set()
    def _collect_depths(cell):
        depths.add(cell.depth)
        for child in cell.children:
            _collect_depths(child)
    _collect_depths(spec.root_cell)

    phase_counts = {3: 0, 6: 0, 9: 0}
    def _count_phases(cell):
        if cell.active and cell.root_value in phase_counts:
            phase_counts[cell.root_value] += 1
        for child in cell.children:
            _count_phases(child)
    _count_phases(spec.root_cell)

    total_harmonic = sum(phase_counts.values())
    distribution = {k: v / total_harmonic if total_harmonic > 0 else 0
                    for k, v in phase_counts.items()}

    return {
        "total_cells": total,
        "active_cells": active,
        "active_ratio": spec.active_ratio,
        "phi_ratio_deviation": phi_deviation,
        "depth_levels": len(depths),
        "kukulcan_alignment": len(depths) >= 9,
        "harmonic_distribution": distribution,
        "sumerian_base60_compat": (total % 60 == 0) or (active % 60 == 0),
        "threefold_symmetry": distribution.get(3, 0) > 0,
        "sixfold_symmetry": distribution.get(6, 0) > 0,
        "singularity_present": distribution.get(9, 0) > 0,
    }


def describe(spec: FractalQRSpec) -> str:
    analysis = analyze_mayan_alignment(spec)
    lines = [
        f"═══ FRACTAL QR-CODE 3-6-9 ═══",
        f"Texto:          \"{spec.source_text}\"",
        f"Raiz global:    {spec.global_root} → {spec.global_phase.name}",
        f"Porta:          {'ABERTA' if spec.gate_open else 'FECHADA'}",
        f"Profundidade:   {spec.max_depth} níveis",
        f"Células:        {spec.cell_count} total, {analysis['active_cells']} ativas ({spec.active_ratio:.1%})",
        f"Hash:           {spec.pattern_hash}",
        f"",
        f"Análise de alinhamento civilizacional:",
        f"  Desvio φ:              {analysis['phi_ratio_deviation']:.3f}",
        f"  Níveis (Kukulcán≥9):   {analysis['depth_levels']} {'✓' if analysis['kukulcan_alignment'] else ''}",
        f"  Simetria 3-fold:       {'✓' if analysis['threefold_symmetry'] else '✗'}",
        f"  Simetria 6-fold:       {'✓' if analysis['sixfold_symmetry'] else '✗'}",
        f"  Singularidade (9):     {'✓' if analysis['singularity_present'] else '✗'}",
        f"  Base-60 (Suméria):     {'✓' if analysis['sumerian_base60_compat'] else '✗'}",
        f"  Distribuição 3/6/9:    {analysis['harmonic_distribution']}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    for phrase in ["O amor liberta e guia", "A Semente de Enoque", "Fear and control"]:
        spec = generate_fractal_qr(phrase)
        print(describe(spec))
        print()
