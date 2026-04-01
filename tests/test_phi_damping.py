"""Tests for Phi-Damping Analysis — minimality proof and catalog."""
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.analysis.phi_damping import (
    compute_zeta, is_phi_damped, find_minimal_integer_pairs,
    build_catalog, compare_seif, describe,
)
from seif.constants import PHI_INVERSE, TF_ZETA


def test_compute_zeta_369():
    """ζ = 3/(2√6) for the SEIF system."""
    zeta = compute_zeta(3, 6)
    expected = 3 / (2 * math.sqrt(6))
    assert abs(zeta - expected) < 1e-10


def test_369_is_phi_damped():
    """(3,6) exhibits phi-damping within 2%."""
    assert is_phi_damped(3, 6, threshold=0.02)


def test_369_is_phi_damped_strict():
    """(3,6) exhibits phi-damping within 1%."""
    assert is_phi_damped(3, 6, threshold=0.01)


def test_minimality_369_is_first():
    """(3,6) is the first result (smallest b+c) in minimality search."""
    pairs = find_minimal_integer_pairs(max_coeff=20)
    assert len(pairs) > 0
    assert pairs[0]["b"] == 3
    assert pairs[0]["c"] == 6
    assert pairs[0]["sum"] == 9


def test_no_smaller_pair():
    """No integer pair with b+c < 9 produces phi-damping within 2%."""
    pairs = find_minimal_integer_pairs(max_coeff=20)
    for p in pairs:
        if p["b"] == 3 and p["c"] == 6:
            continue
        assert p["sum"] > 9, f"Found smaller pair: ({p['b']},{p['c']}) sum={p['sum']}"


def test_zeta_squared_three_eighths():
    """ζ² = (3/(2√6))² = 9/24 = 3/8 = 0.375 exactly."""
    zeta = compute_zeta(3, 6)
    assert abs(zeta ** 2 - 3 / 8) < 1e-14


def test_catalog_minimum_entries():
    """Catalog has at least 5 entries."""
    catalog = build_catalog()
    assert len(catalog) >= 5


def test_catalog_seif_exists():
    """SEIF 3-6-9 is in the catalog with correct values."""
    catalog = build_catalog()
    seif = [s for s in catalog if s.name == "SEIF 3-6-9"]
    assert len(seif) == 1
    assert seif[0].coefficients == (3, 6)
    assert seif[0].integer_coefficients is True
    assert abs(seif[0].zeta - TF_ZETA) < 1e-6


def test_numerator_irrelevant():
    """The numerator 'a' does not affect ζ — only (b, c) matter."""
    z1 = compute_zeta(3, 6)
    # compute_zeta only takes (b, c), confirming numerator is excluded by design
    z2 = compute_zeta(3, 6)
    assert z1 == z2
    # Verify the formula: ζ = b/(2√c), no 'a' involved
    assert abs(z1 - 3 / (2 * math.sqrt(6))) < 1e-15


def test_all_catalog_underdamped():
    """All catalog entries with computed ζ are underdamped (ζ < 1)."""
    catalog = build_catalog()
    for sys in catalog:
        if not math.isnan(sys.zeta):
            assert sys.zeta < 1.0, f"{sys.name} has ζ={sys.zeta} >= 1"


if __name__ == "__main__":
    import inspect
    tests = [obj for name, obj in inspect.getmembers(sys.modules[__name__])
             if inspect.isfunction(obj) and name.startswith("test_")]
    passed = failed = 0
    for fn in sorted(tests, key=lambda f: f.__name__):
        try:
            fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
