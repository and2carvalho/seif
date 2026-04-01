"""Tests for the Transfer Function analysis — proving ζ ≈ φ⁻¹."""
import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.core.transfer_function import (
    analyze, impulse_response, step_response, frequency_response,
    ZETA, PHI_INV, OMEGA_N, OMEGA_D, NUMERATOR, NATURAL_FREQ_SQ,
)
import numpy as np


def test_zeta_approximately_phi_inverse():
    """The central proof: ζ ≈ φ⁻¹ with < 1% deviation."""
    deviation = abs(ZETA - PHI_INV) / PHI_INV
    assert deviation < 0.01, f"ζ={ZETA}, φ⁻¹={PHI_INV}, deviation={deviation:.4%}"


def test_system_is_underdamped():
    assert ZETA < 1.0


def test_omega_n_is_sqrt_6():
    assert abs(OMEGA_N - math.sqrt(6)) < 1e-10


def test_omega_d_positive():
    assert OMEGA_D > 0


def test_dc_gain_is_1_5():
    dc = NUMERATOR / NATURAL_FREQ_SQ
    assert abs(dc - 1.5) < 1e-10


def test_impulse_response_starts_at_zero():
    t = np.array([0.0])
    h = impulse_response(t)
    assert abs(h[0]) < 1e-10


def test_impulse_response_decays():
    t = np.linspace(0, 20, 100)
    h = impulse_response(t)
    assert abs(h[-1]) < abs(h[5])


def test_step_response_settles_at_dc_gain():
    t = np.linspace(0, 30, 1000)
    y = step_response(t)
    dc = NUMERATOR / NATURAL_FREQ_SQ
    assert abs(y[-1] - dc) < 0.01


def test_frequency_response_has_peak():
    omega = np.logspace(-1, 1, 500)
    mag, _ = frequency_response(omega)
    peak_idx = np.argmax(mag)
    # Peak at ωp = ωn√(1-2ζ²) ≈ 1.22 for underdamped system
    assert 0.8 < omega[peak_idx] < 2.0


def test_analyze_returns_phi_aligned():
    a = analyze()
    assert a.is_phi_aligned is True
    assert a.deviation_pct < 1.0
    assert a.system_type == "underdamped"


def test_369_squared_always_reduce_to_9():
    """3²=9, 6²=36→9, 9²=81→9 — the autocorrection property."""
    def dr(n):
        while n > 9:
            n = sum(int(d) for d in str(n))
        return n
    assert dr(3**2) == 9
    assert dr(6**2) == 9
    assert dr(9**2) == 9


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
