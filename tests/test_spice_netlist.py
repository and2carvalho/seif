"""Tests for the SPICE Netlist Generator."""

import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from seif.generators.spice_netlist import (
    compute_components,
    generate_basic,
    generate_from_artifact,
    _spice_value,
    _parse_value,
)
from seif.constants import TF_ZETA, FREQ_TESLA


def test_component_values_432hz():
    """Components at 432 Hz must satisfy H(s) = 9/(s²+3s+6)."""
    comp = compute_components(432)
    omega = 2 * math.pi * 432

    # Verify ωn² = 1/LC
    lc_product = comp.inductance_henry * comp.capacitance_farad
    omega_sq_from_lc = 1.0 / lc_product
    assert abs(omega_sq_from_lc - omega**2) / omega**2 < 1e-6

    # Verify ζ = R/(2√(L/C))
    zeta_from_rlc = comp.resistance_ohm / (2 * math.sqrt(comp.inductance_henry / comp.capacitance_farad))
    assert abs(zeta_from_rlc - TF_ZETA) < 1e-6


def test_component_values_438hz():
    """Components at 438 Hz (Giza) also satisfy ζ = √6/4."""
    comp = compute_components(438)
    zeta_from_rlc = comp.resistance_ohm / (2 * math.sqrt(comp.inductance_henry / comp.capacitance_farad))
    assert abs(zeta_from_rlc - TF_ZETA) < 1e-6


def test_zeta_is_sqrt6_over_4():
    """ζ must always be √6/4 regardless of target frequency."""
    for freq in [100, 432, 438, 1000, 7830]:
        comp = compute_components(freq)
        assert abs(comp.zeta - math.sqrt(6) / 4) < 1e-10


def test_q_factor():
    """Q = 1/(2ζ) = 2/√6."""
    comp = compute_components(432)
    expected_q = 1.0 / (2 * TF_ZETA)
    assert abs(comp.q_factor - expected_q) < 1e-10


def test_dc_gain_is_3_over_2():
    """DC gain = 9/6 = 3/2."""
    comp = compute_components(432)
    assert comp.dc_gain == 1.5


def test_generate_basic_has_netlist():
    """Basic generation produces valid SPICE netlist text."""
    netlist = generate_basic(432)
    assert ".END" in netlist.netlist_text
    assert "V1" in netlist.netlist_text
    assert "R1" in netlist.netlist_text
    assert "L1" in netlist.netlist_text
    assert "C1" in netlist.netlist_text
    assert ".AC" in netlist.netlist_text
    assert ".TRAN" in netlist.netlist_text
    assert "432" in netlist.netlist_text


def test_generate_basic_has_nodes():
    """Basic netlist has 4 nodes (V, R, L, C)."""
    netlist = generate_basic(432)
    assert len(netlist.nodes) == 4
    types = {n.component_type for n in netlist.nodes}
    assert types == {"V", "R", "L", "C"}


def test_generate_from_artifact_9_nodes():
    """Artifact with 9 nodes produces multi-component circuit."""
    nodes = [
        (0.1, 0.1), (0.5, 0.1), (0.9, 0.1),
        (0.1, 0.5), (0.5, 0.5), (0.9, 0.5),
        (0.1, 0.9), (0.5, 0.9), (0.9, 0.9),
    ]
    netlist = generate_from_artifact(nodes, 0.724, 1.885, 432, "test")
    assert ".END" in netlist.netlist_text
    assert "V1" in netlist.netlist_text
    assert netlist.artifact_source == "test"
    assert len(netlist.nodes) >= 3  # at least source + 2 components


def test_generate_from_artifact_fallback():
    """Fewer than 3 nodes falls back to basic circuit."""
    netlist = generate_from_artifact([(0.5, 0.5)], 0.5, 1.5, 432)
    assert "Series RLC" in netlist.netlist_text


def test_spice_value_formatting():
    """SPICE value formatting produces valid strings."""
    assert _spice_value(100) == "100"
    assert "m" in _spice_value(0.1)
    assert "u" in _spice_value(1e-6)
    assert "n" in _spice_value(1e-9)
    assert "p" in _spice_value(1e-12)


def test_parse_value_roundtrip():
    """Formatted values can be parsed back approximately."""
    for val in [332.4, 0.1, 1.357e-6, 33e-9]:
        formatted = _spice_value(val)
        parsed = _parse_value(formatted)
        assert abs(parsed - val) / val < 0.01  # within 1%


def test_frequency_scaling():
    """Different frequencies produce different R, C but same ζ."""
    c1 = compute_components(432)
    c2 = compute_components(438)
    assert c1.resistance_ohm != c2.resistance_ohm
    assert c1.capacitance_farad != c2.capacitance_farad
    assert abs(c1.zeta - c2.zeta) < 1e-10  # same ζ


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
