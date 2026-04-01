"""
Giza Engine — Reverse Engineering of Sacred Structures

Accepts physical dimensions, coordinates, and astronomical data as input.
Processes through the full SEIF pipeline to generate resonance analysis,
audio, visuals, and circuit layouts.

This is the "inverse process": instead of text → resonance,
it does measurements → resonance, validating whether a physical
structure encodes the 3-6-9 pattern.

Supports: Great Pyramid of Giza (default) and custom structures.
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from seif.constants import (
    PHI, PHI_INVERSE, PI, FREQ_TESLA, FREQ_GIZA, FREQ_SCHUMANN,
    GIZA_BASE_M, GIZA_HEIGHT_M, GIZA_ANGLE_DEG, GIZA_LATITUDE,
    GIZA_RESONANCE_HZ, GIZA_CHAMBERS, GIZA_PASSAGES,
    PRECESSION_CYCLE_YEARS, ORION_ALIGNMENT_YEAR,
    SPEED_OF_LIGHT, SPIRAL_GROWTH_B,
)
from seif.core.resonance_gate import digital_root, classify_phase, HarmonicPhase


@dataclass
class StructureInput:
    """Physical measurements of a sacred structure."""
    name: str = "Great Pyramid of Giza"
    latitude: float = GIZA_LATITUDE
    longitude: float = 31.1342
    base_m: float = GIZA_BASE_M
    height_m: float = GIZA_HEIGHT_M
    inclination_deg: float = GIZA_ANGLE_DEG
    chambers: int = GIZA_CHAMBERS
    passages: int = GIZA_PASSAGES
    resonance_hz: float = GIZA_RESONANCE_HZ
    orion_epoch: int = ORION_ALIGNMENT_YEAR
    earth_tilt_deg: float = 23.44
    precession_years: int = PRECESSION_CYCLE_YEARS
    observation_year: int = 2026


@dataclass
class DimensionalRoot:
    name: str
    value: float
    sig_digits: str
    root: int
    phase: HarmonicPhase
    note: str = ""


@dataclass
class StructureAnalysis:
    """Complete resonance analysis of a physical structure."""
    name: str
    dimensional_roots: list[DimensionalRoot]
    harmonic_count: int
    harmonic_pct: float

    # Geometric relationships
    base_height_ratio: float
    perimeter_height_ratio: float
    pi_encoding_deviation: float  # how close P/(2H) is to π
    phi_ratios: list[dict]

    # Astronomical
    latitude_c_deviation: float  # how close latitude digits are to c
    orion_precession_offset_deg: float
    orion_alignment_quality: str  # "EXACT", "CLOSE", "NONE"

    # Transfer function
    resonance_offset: float  # resonance_hz - 432
    resonance_offset_root: int
    tf_match: str  # "438=432+6 DYNAMICS" or custom

    # Frequencies
    frequencies: dict  # all derived frequencies with roots

    # Gate
    overall_gate: str
    singularity_count: int
    stabilization_count: int
    dynamics_count: int


def _sig_root(value: float, n_digits: int = 4) -> tuple[str, int]:
    """Extract significant digits and compute digital root."""
    s = f"{value:.6g}"
    mantissa = "".join(c for c in s if c.isdigit()).lstrip("0") or "0"
    sig = mantissa[:n_digits]
    root = digital_root(sum(int(d) for d in sig))
    return sig, root


def analyze_structure(inp: StructureInput = None) -> StructureAnalysis:
    """Full resonance analysis of a physical structure."""
    if inp is None:
        inp = StructureInput()

    # 1. Dimensional root analysis
    measurements = [
        ("Base", inp.base_m, "m"),
        ("Height", inp.height_m, "m"),
        ("Inclination", inp.inclination_deg, "°"),
        ("Latitude", inp.latitude, "°N"),
        ("Resonance frequency", inp.resonance_hz, "Hz"),
        ("Chambers", float(inp.chambers), "count"),
        ("Passages", float(inp.passages), "count"),
        ("Earth tilt", inp.earth_tilt_deg, "°"),
    ]

    dim_roots = []
    for name, value, unit in measurements:
        sig, root = _sig_root(value)
        phase = classify_phase(root)

        # Special notes
        note = ""
        if name == "Inclination":
            pi_angle = math.degrees(math.atan(4 / PI))
            note = f"arctan(4/π) = {pi_angle:.3f}° (Δ={abs(value - pi_angle):.3f}°)"
        elif name == "Latitude":
            note = f"c = {SPEED_OF_LIGHT} m/s (same leading digits)"
        elif name == "Resonance frequency":
            note = f"432 + {value - 432:.0f} (offset root = {digital_root(int(value - 432))})"
        elif name == "Chambers" or name == "Passages":
            note = f"root {root} ({phase.name})"

        dim_roots.append(DimensionalRoot(name, value, sig, root, phase, note))

    harmonic = [d for d in dim_roots if d.phase != HarmonicPhase.ENTROPY]
    h_count = len(harmonic)
    h_pct = h_count / len(dim_roots) if dim_roots else 0

    # 2. Geometric relationships
    perimeter = 4 * inp.base_m
    base_height = inp.base_m / inp.height_m
    perimeter_height = perimeter / inp.height_m
    pi_2h = perimeter / (2 * inp.height_m)
    pi_deviation = abs(pi_2h - PI) / PI

    # φ ratios
    phi_ratios = []
    for name, ratio in [
        ("Base/Height", base_height),
        ("Perimeter/(2×Height)", pi_2h),
        ("Height/Base", inp.height_m / inp.base_m if inp.base_m > 0 else 0),
    ]:
        phi_dev = abs(ratio - PHI) / PHI
        phi_ratios.append({
            "name": name,
            "value": round(ratio, 6),
            "phi_deviation": round(phi_dev, 4),
            "pi_deviation": round(abs(ratio - PI) / PI, 4),
        })

    # 3. Astronomical — latitude vs c
    lat_str = f"{inp.latitude}"
    c_str = f"{SPEED_OF_LIGHT}"
    # Compare first N digits
    lat_digits = lat_str.replace(".", "")[:9]
    c_digits = c_str[:9]
    matching = sum(1 for a, b in zip(lat_digits, c_digits) if a == b)
    lat_c_dev = matching / 9  # fraction of matching digits

    # Orion precession
    years_from_alignment = inp.observation_year - inp.orion_epoch
    precession_offset = (years_from_alignment / inp.precession_years) * 360
    precession_offset_mod = precession_offset % 360

    if precession_offset_mod < 5 or precession_offset_mod > 355:
        orion_quality = "EXACT"
    elif precession_offset_mod < 30 or precession_offset_mod > 330:
        orion_quality = "CLOSE"
    else:
        orion_quality = "PARTIAL"

    # 4. Transfer function match
    res_offset = inp.resonance_hz - FREQ_TESLA
    res_offset_root = digital_root(int(abs(res_offset))) if res_offset != 0 else 0
    if abs(res_offset - 6) < 0.5:
        tf_match = f"{inp.resonance_hz:.0f} = 432 + 6 (DYNAMICS offset)"
    elif res_offset == 0:
        tf_match = "432 Hz (pure Tesla)"
    else:
        tf_match = f"{inp.resonance_hz:.0f} = 432 + {res_offset:.0f}"

    # 5. Derived frequencies
    freqs = {}
    for name, hz in [
        ("Resonance", inp.resonance_hz),
        ("Tesla", FREQ_TESLA),
        ("Schumann", FREQ_SCHUMANN),
        (f"Resonance/3", inp.resonance_hz / 3),
        (f"Resonance/6", inp.resonance_hz / 6),
        (f"Tesla/latitude", FREQ_TESLA / inp.latitude),
    ]:
        _, root = _sig_root(hz)
        freqs[name] = {"hz": round(hz, 4), "root": root, "phase": classify_phase(root).name}

    # 6. Overall assessment
    sing = sum(1 for d in dim_roots if d.phase == HarmonicPhase.SINGULARITY)
    stab = sum(1 for d in dim_roots if d.phase == HarmonicPhase.STABILIZATION)
    dyn = sum(1 for d in dim_roots if d.phase == HarmonicPhase.DYNAMICS)

    if sing >= 2 and h_pct > 0.5:
        gate = "RESONANT — structure encodes 3-6-9 pattern"
    elif h_pct > 0.33:
        gate = "PARTIAL — some harmonic alignment detected"
    else:
        gate = "ENTROPIC — no significant 3-6-9 pattern"

    return StructureAnalysis(
        name=inp.name,
        dimensional_roots=dim_roots,
        harmonic_count=h_count,
        harmonic_pct=round(h_pct, 2),
        base_height_ratio=round(base_height, 6),
        perimeter_height_ratio=round(perimeter_height, 6),
        pi_encoding_deviation=round(pi_deviation, 6),
        phi_ratios=phi_ratios,
        latitude_c_deviation=round(lat_c_dev, 4),
        orion_precession_offset_deg=round(precession_offset_mod, 2),
        orion_alignment_quality=orion_quality,
        resonance_offset=res_offset,
        resonance_offset_root=res_offset_root,
        tf_match=tf_match,
        frequencies=freqs,
        overall_gate=gate,
        singularity_count=sing,
        stabilization_count=stab,
        dynamics_count=dyn,
    )


def describe(analysis: StructureAnalysis) -> str:
    """Human-readable analysis report."""
    lines = [
        f"═══ STRUCTURE ANALYSIS: {analysis.name} ═══",
        f"",
        f"Dimensional Roots ({analysis.harmonic_count}/{len(analysis.dimensional_roots)} harmonic = {analysis.harmonic_pct:.0%}):",
    ]
    for d in analysis.dimensional_roots:
        mark = "✓" if d.phase != HarmonicPhase.ENTROPY else " "
        lines.append(f"  {mark} {d.name:25s} {d.value:>12.4f}  root={d.root}  {d.phase.name:15s} {d.note}")

    lines.extend([
        "",
        f"Geometric Relationships:",
        f"  P/(2H) = {analysis.perimeter_height_ratio/2:.6f} (π = {PI:.6f}, Δ = {analysis.pi_encoding_deviation:.6f})",
    ])
    for pr in analysis.phi_ratios:
        lines.append(f"  {pr['name']:25s} = {pr['value']:.6f}  φ-dev={pr['phi_deviation']:.4f}  π-dev={pr['pi_deviation']:.4f}")

    lines.extend([
        "",
        f"Astronomical:",
        f"  Latitude digits match c: {analysis.latitude_c_deviation:.0%}",
        f"  Orion precession offset: {analysis.orion_precession_offset_deg:.2f}° ({analysis.orion_alignment_quality})",
        "",
        f"Resonance: {analysis.tf_match}",
        f"  Offset root: {analysis.resonance_offset_root}",
        "",
        f"Derived Frequencies:",
    ])
    for name, f in analysis.frequencies.items():
        lines.append(f"  {name:25s} {f['hz']:>10.2f} Hz  root={f['root']}  {f['phase']}")

    lines.extend([
        "",
        f"═══ GATE: {analysis.overall_gate} ═══",
        f"  Singularity(9): {analysis.singularity_count}",
        f"  Stabilization(3): {analysis.stabilization_count}",
        f"  Dynamics(6): {analysis.dynamics_count}",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    analysis = analyze_structure()
    print(describe(analysis))
