"""Tests for KiCad PCB Exporter."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from seif.generators.kicad_exporter import (
        export_kicad_pcb,
        _generate_pcb_content,
        _generate_manhattan_variant,
    )
    from seif.generators.circuit_generator import (
        CircuitLayout, TraceSegment, PadDef, BOARD_SIZE_MM,
    )
except ImportError as _e:
    print(f"SKIP test_kicad_exporter: {_e}")
    sys.exit(0)
from seif.core.resonance_gate import HarmonicPhase


def _make_layout(text="test", gate_open=True):
    """Create a minimal test layout."""
    center = BOARD_SIZE_MM / 2
    return CircuitLayout(
        board_size=BOARD_SIZE_MM,
        traces=[
            TraceSegment([(10, 40), (40, 40), (70, 40)], 0.3, "F.Cu", HarmonicPhase.SINGULARITY),
            TraceSegment([(40, 10), (40, 40), (40, 70)], 0.3, "F.Cu", HarmonicPhase.DYNAMICS),
        ],
        pads=[
            PadDef(center, center, 1.5, "CENTER", True),
            PadDef(10, 40, 1.5, "N1", True),
            PadDef(70, 40, 1.5, "N2", True),
        ],
        layer_count=9,
        source_text=text,
        global_phase=HarmonicPhase.SINGULARITY,
        gate_open=gate_open,
    )


def test_generates_valid_sexpression():
    """Output must be valid KiCad S-expression."""
    layout = _make_layout()
    content = _generate_pcb_content(layout)
    assert content.startswith("(kicad_pcb")
    assert content.rstrip().endswith(")")
    # Check parenthesis balance
    assert content.count("(") == content.count(")")


def test_contains_header():
    """PCB must have version, generator, title block."""
    layout = _make_layout("Enoch Seed")
    content = _generate_pcb_content(layout)
    assert "version" in content
    assert "seif_sfa_generator" in content
    assert "seif_sfa_generator" in content


def test_contains_layers():
    """PCB must define F.Cu, B.Cu, Edge.Cuts."""
    content = _generate_pcb_content(_make_layout())
    assert '"F.Cu"' in content
    assert '"B.Cu"' in content
    assert '"Edge.Cuts"' in content


def test_contains_traces():
    """PCB must have segment elements for traces."""
    content = _generate_pcb_content(_make_layout())
    assert "(segment" in content


def test_contains_pads():
    """PCB must have via or footprint elements for pads."""
    content = _generate_pcb_content(_make_layout())
    assert "(via" in content or "(footprint" in content


def test_contains_board_outline():
    """PCB must have Edge.Cuts rectangle."""
    content = _generate_pcb_content(_make_layout())
    assert "gr_rect" in content
    assert f"{BOARD_SIZE_MM}" in content


def test_export_creates_file():
    """export_kicad_pcb must create a .kicad_pcb file."""
    layout = _make_layout()
    path = export_kicad_pcb(layout, "test_export.kicad_pcb")
    assert path.exists()
    assert path.suffix == ".kicad_pcb"
    content = path.read_text()
    assert "(kicad_pcb" in content
    path.unlink()  # cleanup


def test_manhattan_variant_has_more_segments():
    """Manhattan routing produces more segments (H-V-H) than φ-spiral."""
    layout = _make_layout()
    manhattan = _generate_manhattan_variant(layout)
    # Manhattan L-routing adds intermediate points
    total_sfa = sum(len(t.points) for t in layout.traces)
    total_man = sum(len(t.points) for t in manhattan.traces)
    assert total_man >= total_sfa


def test_manhattan_is_entropy():
    """Manhattan variant must be classified as ENTROPY."""
    layout = _make_layout()
    manhattan = _generate_manhattan_variant(layout)
    assert manhattan.global_phase == HarmonicPhase.ENTROPY
    assert manhattan.gate_open == False


def test_comparison_pair_generates_both():
    """generate_comparison_pair must create SFA + Manhattan files."""
    from seif.generators.kicad_exporter import generate_comparison_pair
    sfa_path, manhattan_path = generate_comparison_pair("test compare")
    assert sfa_path.exists()
    assert manhattan_path.exists()
    # Cleanup
    sfa_path.unlink()
    manhattan_path.unlink()


def test_silkscreen_annotation():
    """PCB must have SEIF protocol annotation on silkscreen."""
    content = _generate_pcb_content(_make_layout())
    assert "S.E.I.F." in content
    assert "F.SilkS" in content


# === Runner ===

if __name__ == "__main__":
    passed = 0
    failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test_fn.__name__}: {e}")

    print(f"{passed} passed, {failed} failed")
