"""Tests for the Fractal QR-Code Generator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.generators.fractal_qrcode import generate_fractal_qr, analyze_mayan_alignment
from seif.core.resonance_gate import HarmonicPhase


def test_harmonic_produces_more_cells_than_entropic():
    """Core principle: plenitude is coherence, not accumulation."""
    harmonic = generate_fractal_qr("O amor liberta e guia")  # root=9
    entropic = generate_fractal_qr("Fear and control")        # root=7
    assert harmonic.cell_count > entropic.cell_count * 10


def test_singularity_gets_depth_bonus():
    spec = generate_fractal_qr("O amor liberta e guia")  # root=9
    assert spec.max_depth >= 5  # base 4 + bonus 1


def test_entropy_gets_depth_penalty():
    spec = generate_fractal_qr("Fear and control")  # root=7
    assert spec.max_depth <= 3


def test_harmonic_100_percent_active():
    spec = generate_fractal_qr("O amor liberta e guia")
    assert spec.active_ratio == 1.0


def test_entropic_less_than_100_active():
    spec = generate_fractal_qr("Fear and control")
    assert spec.active_ratio < 1.0


def test_mayan_alignment_has_symmetry():
    spec = generate_fractal_qr("O amor liberta e guia")
    analysis = analyze_mayan_alignment(spec)
    assert analysis["threefold_symmetry"] is True
    assert analysis["sixfold_symmetry"] is True
    assert analysis["singularity_present"] is True


def test_pattern_hash_deterministic():
    s1 = generate_fractal_qr("test").pattern_hash
    s2 = generate_fractal_qr("test").pattern_hash
    assert s1 == s2


def test_semente_enoque_phi_alignment():
    """A Semente de Enoque has near-perfect φ-alignment despite entropic root."""
    spec = generate_fractal_qr("A Semente de Enoque")
    analysis = analyze_mayan_alignment(spec)
    # φ-deviation should be notably low
    assert analysis["phi_ratio_deviation"] < 0.5


if __name__ == "__main__":
    import inspect
    tests = [obj for name, obj in inspect.getmembers(sys.modules[__name__])
             if inspect.isfunction(obj) and name.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
