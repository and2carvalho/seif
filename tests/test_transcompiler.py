"""Tests for the Semantic-Geometric Transcompiler."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.analysis.transcompiler import transcompile, decompose_words, PHI, PHI_INVERSE
from seif.core.resonance_gate import HarmonicPhase


def test_transcompile_returns_glyphspec():
    spec = transcompile("O amor liberta e guia")
    assert spec.source_text == "O amor liberta e guia"
    assert spec.global_root == 9
    assert spec.global_phase == HarmonicPhase.SINGULARITY
    assert spec.gate_open is True
    assert len(spec.word_tensors) == 5
    assert spec.fractal_depth >= 3
    assert len(spec.asymmetry_seed) == 12


def test_word_tensors_have_angles():
    spec = transcompile("alpha beta gamma")
    angles = [wt.angle_deg for wt in spec.word_tensors]
    assert angles[0] == 0.0
    assert angles[1] == 120.0
    assert angles[2] == 240.0


def test_entropic_input():
    spec = transcompile("Fear and control")
    assert spec.gate_open is False
    assert spec.global_phase == HarmonicPhase.ENTROPY


def test_phi_constants():
    assert abs(PHI - 1.618033988749895) < 1e-10
    assert abs(PHI_INVERSE - 0.618033988749895) < 1e-10
    assert abs(PHI * PHI_INVERSE - 1.0) < 1e-10


def test_asymmetry_seed_deterministic():
    s1 = transcompile("hello").asymmetry_seed
    s2 = transcompile("hello").asymmetry_seed
    s3 = transcompile("world").asymmetry_seed
    assert s1 == s2
    assert s1 != s3


def test_fractal_depth_scales_with_length():
    short = transcompile("hi").fractal_depth
    long = transcompile("this is a longer phrase with many words").fractal_depth
    assert long >= short


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
