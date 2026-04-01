"""
KiCad PCB Exporter — Convert CircuitLayout to .kicad_pcb format

Exports the same φ-spiral layout used by the SVG generator into KiCad's
native PCB format (S-expression .kicad_pcb). The output can be:
  - Opened in KiCad PCB Editor for manual refinement
  - Sent directly to fabrication (JLCPCB, PCBWay, etc.) after DRC
  - Used for thermal and electrical simulation comparison vs 90° routing

Also generates a conventional 90° (Manhattan) version of the same circuit
for A/B comparison. This enables the key measurement:
  "Does φ-spiral routing measurably differ from conventional routing?"

Stance: The layout generation is formal-symbolic (same algorithm as SVG).
The hypothesis that φ-spirals improve performance is empirical-observational.
"""

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.generators.circuit_generator import (
    CircuitLayout, TraceSegment, PadDef,
    _phi_spiral_points, _hex_ring_positions, _resonance_seal_traces,
    BOARD_SIZE_MM, TRACE_WIDTH_MM, PAD_DIAMETER_MM, VIA_DIAMETER_MM,
    SPIRAL_TURNS,
)
from seif.core.resonance_gate import HarmonicPhase

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output" / "circuits"

# KiCad layer IDs
KICAD_LAYERS = {
    "F.Cu": 0,
    "B.Cu": 31,
    "F.SilkS": 37,
    "B.SilkS": 38,
    "F.Fab": 40,
    "B.Fab": 41,
    "Edge.Cuts": 44,
}

PHASE_TO_LAYER = {
    HarmonicPhase.SINGULARITY: "F.Cu",
    HarmonicPhase.STABILIZATION: "F.Cu",
    HarmonicPhase.DYNAMICS: "B.Cu",
    HarmonicPhase.ENTROPY: "F.Cu",
}


def export_kicad_pcb(layout: CircuitLayout,
                     filename: Optional[str] = None,
                     include_90deg_comparison: bool = False) -> Path:
    """Export CircuitLayout as .kicad_pcb file.

    Args:
        layout: The circuit layout (from generate_from_spec or manual).
        filename: Output filename (default: auto from source_text).
        include_90deg_comparison: If True, also generates a Manhattan-routed
                                  version for A/B comparison.

    Returns:
        Path to the generated .kicad_pcb file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in layout.source_text)
        filename = f"sfa_{safe[:40]}.kicad_pcb"

    content = _generate_pcb_content(layout)
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")

    if include_90deg_comparison:
        manhattan = _generate_manhattan_variant(layout)
        manhattan_content = _generate_pcb_content(manhattan)
        manhattan_path = OUTPUT_DIR / filename.replace(".kicad_pcb", "_90deg.kicad_pcb")
        manhattan_path.write_text(manhattan_content, encoding="utf-8")

    return path


def _generate_pcb_content(layout: CircuitLayout) -> str:
    """Generate KiCad PCB S-expression content."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    board = layout.board_size

    parts = []

    # Header + layers + setup (minimal valid KiCad 9 format)
    parts.append(f"""\
(kicad_pcb
  (version 20240108)
  (generator "seif_sfa_generator")
  (generator_version "1.0")
  (general
    (thickness 1.6)
    (legacy_teardrops no)
  )
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (36 "B.SilkS" user "B.Silkscreen")
    (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user "B.Mask")
    (39 "F.Mask" user "F.Mask")
    (44 "Edge.Cuts" user)
  )
  (setup
    (pad_to_mask_clearance 0.05)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (outputdirectory "gerber/")
    )
  )
  (net 0 "")
  (net 1 "SEIF")
  (gr_rect
    (start 0 0)
    (end {board} {board})
    (stroke (width 0.15) (type default))
    (fill none)
    (layer "Edge.Cuts")
  )""")

    # Traces
    for i, trace in enumerate(layout.traces):
        layer = PHASE_TO_LAYER.get(trace.phase, trace.layer)
        width = trace.width
        net = 1  # simplified: all on net 1

        for j in range(len(trace.points) - 1):
            x1, y1 = trace.points[j]
            x2, y2 = trace.points[j + 1]
            parts.append(
                f'  (segment (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) '
                f'(width {width}) (layer "{layer}") (net {net}))'
            )

    # Pads as vias (through-hole, visible on both layers)
    for i, pad in enumerate(layout.pads):
        ref = pad.label or f"P{i+1}"
        parts.append(
            f'  (via (at {pad.x:.4f} {pad.y:.4f}) (size {pad.diameter}) '
            f'(drill {pad.diameter * 0.4:.4f}) (layers "F.Cu" "B.Cu") (net 1))'
        )
        # Label on silkscreen
        parts.append(
            f'  (gr_text "{ref}" (at {pad.x:.4f} {pad.y - pad.diameter:.4f}) '
            f'(layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.15))))'
        )

    # Silkscreen annotations
    center = board / 2
    parts.append(
        f'  (gr_text "S.E.I.F. SFA | {layout.global_phase.name}" '
        f'(at {center} {board - 2}) (layer "F.SilkS") '
        f'(effects (font (size 1.2 1.2) (thickness 0.2))))'
    )

    # Close
    parts.append(")")

    return "\n".join(parts)


def _generate_manhattan_variant(layout: CircuitLayout) -> CircuitLayout:
    """Generate a 90° Manhattan-routed version of the same circuit.

    Same pad positions, same component count, but with straight
    horizontal/vertical traces instead of φ-spirals. This is the
    CONTROL for the A/B comparison experiment.
    """
    manhattan_traces = []

    for trace in layout.traces:
        if len(trace.points) < 2:
            manhattan_traces.append(trace)
            continue

        # Convert φ-spiral path to Manhattan (H-V-H) routing
        manhattan_points = []
        for j in range(len(trace.points) - 1):
            x1, y1 = trace.points[j]
            x2, y2 = trace.points[j + 1]

            # L-shaped: go horizontal first, then vertical
            manhattan_points.append((x1, y1))
            manhattan_points.append((x2, y1))  # horizontal segment
            manhattan_points.append((x2, y2))  # vertical segment

        manhattan_traces.append(TraceSegment(
            points=manhattan_points,
            width=trace.width,
            layer=trace.layer,
            phase=HarmonicPhase.ENTROPY,  # Manhattan = entropic by definition
        ))

    return CircuitLayout(
        board_size=layout.board_size,
        traces=manhattan_traces,
        pads=layout.pads,  # same pad positions
        layer_count=layout.layer_count,
        source_text=layout.source_text + " (90° Manhattan control)",
        global_phase=HarmonicPhase.ENTROPY,
        gate_open=False,
    )


def generate_comparison_pair(source_text: str = "Enoch Seed") -> tuple[Path, Path]:
    """Generate both SFA and Manhattan PCBs from the same source text.

    Returns (sfa_path, manhattan_path) for A/B comparison.
    """
    from seif.analysis.transcompiler import transcompile
    from seif.generators.circuit_generator import generate_from_spec

    spec = transcompile(source_text)
    layout = generate_from_spec(spec)

    sfa_path = export_kicad_pcb(layout, include_90deg_comparison=True)
    manhattan_name = sfa_path.name.replace(".kicad_pcb", "_90deg.kicad_pcb")
    manhattan_path = sfa_path.parent / manhattan_name

    return sfa_path, manhattan_path


if __name__ == "__main__":
    from seif.analysis.transcompiler import transcompile
    from seif.generators.circuit_generator import generate_from_spec

    # Generate SFA + Manhattan comparison for "Enoch Seed"
    print("═══ KiCad PCB Export ═══\n")

    for text in ["Enoch Seed", "Fear and control"]:
        spec = transcompile(text)
        layout = generate_from_spec(spec)

        path = export_kicad_pcb(layout, include_90deg_comparison=True)
        manhattan_path = path.parent / path.name.replace(".kicad_pcb", "_90deg.kicad_pcb")

        print(f'"{text}":')
        print(f"  Phase: {layout.global_phase.name} | Gate: {'OPEN' if layout.gate_open else 'CLOSED'}")
        print(f"  Traces: {len(layout.traces)} | Pads: {len(layout.pads)} | Layers: {layout.layer_count}")
        print(f"  SFA:       {path}")
        print(f"  Manhattan: {manhattan_path}")
        print()
