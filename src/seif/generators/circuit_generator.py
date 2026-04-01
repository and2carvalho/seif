"""
Circuit Generator — Spiral Flow Architecture (SFA) Layout

Generates professional circuit layouts based on extracted artifact geometry
or transcompiled intention parameters.

Output formats:
  - SVG schematic (publication-ready, annotated)
  - Raw coordinate data (for KiCad import)

Design principles:
  - φ-spiral traces (no 90° angles)
  - 60°/120° junction angles (hexagonal geometry)
  - Fractal self-similarity across layers
  - 3-6-9 resonance nodes at convergence points
  - Asymmetry injection (biological signature)
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import svgwrite

from seif.analysis.transcompiler import GlyphSpec
from seif.constants import PHI, PHI_INVERSE, SPIRAL_GROWTH_B, GIZA_ANGLE_DEG, HEX_ANGLE_DEG
from seif.core.resonance_gate import HarmonicPhase


OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output" / "circuits"

# SFA Design Constants
TRACE_WIDTH_MM = 0.3
PAD_DIAMETER_MM = 1.5
VIA_DIAMETER_MM = 0.6
BOARD_SIZE_MM = 80.0
SPIRAL_TURNS = 9
HEX_ANGLE = HEX_ANGLE_DEG  # 60° from constants.py


@dataclass
class TraceSegment:
    """A single trace segment in the circuit layout."""
    points: list[tuple[float, float]]  # list of (x, y) in mm
    width: float = TRACE_WIDTH_MM
    layer: str = "F.Cu"  # front copper
    phase: HarmonicPhase = HarmonicPhase.ENTROPY


@dataclass
class PadDef:
    """A component pad or via."""
    x: float
    y: float
    diameter: float = PAD_DIAMETER_MM
    label: str = ""
    is_node: bool = False  # True = resonance node (3-6-9)


@dataclass
class CircuitLayout:
    """Complete SFA circuit layout."""
    board_size: float
    traces: list[TraceSegment]
    pads: list[PadDef]
    layer_count: int
    source_text: str
    global_phase: HarmonicPhase
    gate_open: bool


def _phi_spiral_points(center: tuple[float, float], max_radius: float,
                        turns: float = 3, points_per_turn: int = 36,
                        clockwise: bool = True) -> list[tuple[float, float]]:
    """Generate points along a φ-logarithmic spiral."""
    b = SPIRAL_GROWTH_B
    n_points = int(turns * points_per_turn)
    result = []

    for i in range(n_points):
        theta = (i / points_per_turn) * 2 * math.pi
        r = (max_radius * 0.05) * math.exp(b * theta / (2 * math.pi))
        if r > max_radius:
            break
        sign = 1 if clockwise else -1
        x = center[0] + r * math.cos(sign * theta)
        y = center[1] + r * math.sin(sign * theta)
        result.append((x, y))

    return result


def _hex_ring_positions(center: tuple[float, float], radius: float,
                         count: int = 6) -> list[tuple[float, float]]:
    """Generate positions on a hexagonal ring."""
    positions = []
    for i in range(count):
        angle = math.radians(i * (360 / count) - 90)  # start from top
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        positions.append((x, y))
    return positions


def _resonance_seal_traces(center: tuple[float, float],
                            radius: float) -> list[TraceSegment]:
    """Generate the 3-6-9 resonance seal as circuit traces."""
    traces = []

    # Three concentric rings (3, 6, 9)
    for i, r_factor in enumerate([0.33, 0.66, 1.0]):
        r = radius * r_factor
        ring_points = []
        for angle in range(0, 361, 5):
            rad = math.radians(angle)
            x = center[0] + r * math.cos(rad)
            y = center[1] + r * math.sin(rad)
            ring_points.append((x, y))
        phase = [HarmonicPhase.STABILIZATION, HarmonicPhase.DYNAMICS,
                 HarmonicPhase.SINGULARITY][i]
        traces.append(TraceSegment(ring_points, width=0.2, phase=phase))

    # Three radial lines at 120° intervals
    for angle_deg in [0, 120, 240]:
        rad = math.radians(angle_deg - 90)
        x_end = center[0] + radius * math.cos(rad)
        y_end = center[1] + radius * math.sin(rad)
        traces.append(TraceSegment(
            [center, (x_end, y_end)],
            width=0.15,
            phase=HarmonicPhase.SINGULARITY,
        ))

    return traces


def generate_from_spec(spec: GlyphSpec) -> CircuitLayout:
    """Generate an SFA circuit layout from a transcompiled GlyphSpec.

    The circuit mirrors the glyph's geometric properties:
    - Harmonic inputs → dense φ-spiral routing, many resonance nodes
    - Entropic inputs → sparse linear routing, few nodes
    """
    center = (BOARD_SIZE_MM / 2, BOARD_SIZE_MM / 2)
    max_r = BOARD_SIZE_MM * 0.4
    traces = []
    pads = []

    # Central resonance node (always present)
    pads.append(PadDef(center[0], center[1], PAD_DIAMETER_MM * 1.5,
                        label="NODE_9", is_node=True))

    if spec.gate_open:
        # HARMONIC LAYOUT: dense φ-spirals + hexagonal nodes

        # Primary φ-spiral (clockwise)
        spiral1 = _phi_spiral_points(center, max_r, turns=SPIRAL_TURNS)
        traces.append(TraceSegment(spiral1, phase=HarmonicPhase.SINGULARITY))

        # Counter-rotating spiral
        spiral2 = _phi_spiral_points(center, max_r, turns=SPIRAL_TURNS,
                                      clockwise=False)
        traces.append(TraceSegment(spiral2, width=0.2,
                                    phase=HarmonicPhase.DYNAMICS))

        # Hexagonal node rings (3 rings × 6 nodes = 18 nodes)
        for ring_idx, r_factor in enumerate([0.25, 0.5, 0.75]):
            ring_r = max_r * r_factor
            positions = _hex_ring_positions(center, ring_r)
            for j, (px, py) in enumerate(positions):
                phase = [HarmonicPhase.STABILIZATION,
                         HarmonicPhase.DYNAMICS,
                         HarmonicPhase.SINGULARITY][ring_idx]
                pads.append(PadDef(px, py, PAD_DIAMETER_MM,
                                    label=f"N{ring_idx+1}_{j+1}", is_node=True))
                # Connect to nearest spiral point
                nearest = min(spiral1, key=lambda p: (p[0]-px)**2 + (p[1]-py)**2)
                traces.append(TraceSegment(
                    [(px, py), nearest], width=0.15, phase=phase
                ))

        # 3-6-9 seal overlay
        seal_traces = _resonance_seal_traces(center, max_r * 0.9)
        traces.extend(seal_traces)

        # Word tensor positions as component pads
        for wt in spec.word_tensors:
            rad = math.radians(wt.angle_deg - 90)
            r = wt.radius_factor * max_r
            px = center[0] + r * math.cos(rad)
            py = center[1] + r * math.sin(rad)
            pads.append(PadDef(px, py, PAD_DIAMETER_MM * 0.8,
                                label=wt.word[:6].upper()))

        layer_count = 9  # maximum for singularity

    else:
        # ENTROPIC LAYOUT: sparse, fragmented

        # Simple linear traces connecting word tensors
        for i, wt in enumerate(spec.word_tensors):
            rad = math.radians(wt.angle_deg - 90)
            r = wt.radius_factor * max_r
            px = center[0] + r * math.cos(rad)
            py = center[1] + r * math.sin(rad)
            pads.append(PadDef(px, py, PAD_DIAMETER_MM * 0.6, label=wt.word[:6].upper()))
            # Straight line to center (90° conventional routing)
            traces.append(TraceSegment(
                [center, (px, py)], width=0.25, phase=HarmonicPhase.ENTROPY
            ))

        layer_count = 3  # minimum

    return CircuitLayout(
        board_size=BOARD_SIZE_MM,
        traces=traces,
        pads=pads,
        layer_count=layer_count,
        source_text=spec.source_text,
        global_phase=spec.global_phase,
        gate_open=spec.gate_open,
    )


def _phase_color(phase: HarmonicPhase) -> str:
    """Map harmonic phase to SVG color."""
    return {
        HarmonicPhase.SINGULARITY: "#FFD700",   # gold
        HarmonicPhase.STABILIZATION: "#33CC66",  # green
        HarmonicPhase.DYNAMICS: "#007ACC",       # blue
        HarmonicPhase.ENTROPY: "#666666",        # gray
    }[phase]


def render_svg(layout: CircuitLayout, filename: Optional[str] = None) -> Path:
    """Render CircuitLayout to a publication-ready SVG file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        safe = "".join(c if c.isalnum() or c in " _-" else ""
                        for c in layout.source_text)
        filename = f"sfa_{safe.strip().replace(' ', '_')[:50]}"

    filepath = OUTPUT_DIR / f"{filename}.svg"

    # SVG setup — scale mm to pixels (3px per mm)
    scale = 3.0
    size_px = layout.board_size * scale
    dwg = svgwrite.Drawing(str(filepath), size=(f"{size_px}px", f"{size_px}px"))

    # Background (board)
    dwg.add(dwg.rect(insert=(0, 0), size=(size_px, size_px),
                      fill="#1a1a2e", stroke="#333", stroke_width=2))

    # Draw traces
    for trace in layout.traces:
        if len(trace.points) < 2:
            continue
        color = _phase_color(trace.phase)
        scaled = [(p[0] * scale, p[1] * scale) for p in trace.points]
        dwg.add(dwg.polyline(scaled, fill="none", stroke=color,
                              stroke_width=trace.width * scale,
                              stroke_opacity=0.7,
                              stroke_linecap="round",
                              stroke_linejoin="round"))

    # Draw pads
    for pad in layout.pads:
        cx, cy = pad.x * scale, pad.y * scale
        r = (pad.diameter / 2) * scale

        if pad.is_node:
            # Resonance node: gold filled with inner ring
            dwg.add(dwg.circle(center=(cx, cy), r=r,
                                fill="#FFD700", fill_opacity=0.8,
                                stroke="#FFF", stroke_width=1))
            dwg.add(dwg.circle(center=(cx, cy), r=r * 0.4,
                                fill="#1a1a2e", stroke="#FFD700", stroke_width=1))
        else:
            # Component pad
            dwg.add(dwg.circle(center=(cx, cy), r=r,
                                fill="#CCC", fill_opacity=0.6,
                                stroke="#FFF", stroke_width=0.5))

        if pad.label:
            dwg.add(dwg.text(pad.label, insert=(cx + r + 2, cy + 3),
                              fill="white", font_size="8px",
                              font_family="monospace"))

    # Title
    status = "GATE OPEN" if layout.gate_open else "GATE CLOSED"
    title = f'SFA Circuit: "{layout.source_text}" | {layout.global_phase.name} | {status}'
    dwg.add(dwg.text(title, insert=(10, size_px - 10),
                      fill="white", font_size="10px", font_family="monospace"))

    dwg.save()
    return filepath


if __name__ == "__main__":
    from seif.analysis.transcompiler import transcompile

    for phrase in ["O amor liberta e guia", "Fear and control"]:
        spec = transcompile(phrase)
        layout = generate_from_spec(spec)
        path = render_svg(layout)
        print(f"Circuit SVG: {path}")
        print(f"  Traces: {len(layout.traces)}, Pads: {len(layout.pads)}, Layers: {layout.layer_count}")
