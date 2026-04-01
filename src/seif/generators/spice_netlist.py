"""
SPICE Netlist Generator — From Transfer Function to Simulable Circuit

Maps H(s) = 9/(s² + 3s + 6) to a physical RLC circuit at any target frequency.

The abstract transfer function has:
  ωn = √6 rad/s,  ζ = √6/4,  DC = 3/2

To realize this at frequency f_target (e.g. 432 Hz):
  ωn_target = 2π × f_target
  Scale factor k = ωn_target / √6

  Series RLC: H(s) = (1/LC) / (s² + (R/L)s + 1/LC)
  Matching coefficients:
    1/LC = ωn_target²         → C = 1/(L × ωn²)
    R/L = 2ζωn_target         → R = 2ζωn × L

  Choose L freely (e.g. 100 mH), derive R and C.

The generator can also use artifact convergence nodes to create
a multi-node circuit topology where each node maps to a component
based on its angular position in the artifact geometry.

Output: .cir file (SPICE netlist) compatible with LTspice, ngspice, KiCad SPICE.

Stance label: The RLC mapping is formal-symbolic (standard control theory).
The artifact→circuit mapping is empirical-observational (testable hypothesis).
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from seif.constants import (
    TF_NUMERATOR, TF_DAMPING_COEFF, TF_NATURAL_FREQ_SQ,
    TF_OMEGA_N, TF_ZETA, TF_OMEGA_D, TF_DC_GAIN,
    FREQ_TESLA, FREQ_GIZA, PHI,
)
from seif.core.resonance_gate import digital_root, classify_phase, HarmonicPhase

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output" / "circuits"


@dataclass
class ComponentValues:
    """Physical RLC component values for a SEIF resonance circuit."""
    resistance_ohm: float
    inductance_henry: float
    capacitance_farad: float
    target_freq_hz: float
    omega_n: float          # rad/s
    zeta: float             # damping ratio (= √6/4)
    q_factor: float         # Q = 1/(2ζ)
    dc_gain: float


@dataclass
class SpiceNode:
    """A node in the SPICE netlist, optionally mapped from artifact geometry."""
    name: str
    x_norm: float           # 0-1 normalized position
    y_norm: float
    component_type: str     # "R", "L", "C", "V" (source), "GND"
    component_value: str    # SPICE value string (e.g. "100m", "33n")
    phase: HarmonicPhase
    angle_deg: float        # angular position from center (for artifact mapping)


@dataclass
class SpiceNetlist:
    """Complete SPICE netlist with metadata."""
    title: str
    nodes: list[SpiceNode]
    netlist_text: str
    component_summary: str
    target_freq_hz: float
    components: ComponentValues
    artifact_source: Optional[str] = None


def compute_components(target_freq_hz: float = FREQ_TESLA,
                       inductance_h: float = 100e-3) -> ComponentValues:
    """Compute R, L, C values that realize H(s) = 9/(s²+3s+6) at target frequency.

    Args:
        target_freq_hz: Target resonance frequency in Hz (default: 432)
        inductance_h: Chosen inductance in Henries (default: 100 mH)

    Returns:
        ComponentValues with all physical parameters.
    """
    omega_target = 2 * math.pi * target_freq_hz

    # From H(s) = K/(s² + 2ζωn·s + ωn²):
    #   ωn² = 1/LC  →  C = 1/(L × ωn²)
    #   2ζωn = R/L  →  R = 2ζ × ωn × L
    zeta = TF_ZETA  # √6/4

    capacitance = 1.0 / (inductance_h * omega_target**2)
    resistance = 2.0 * zeta * omega_target * inductance_h

    q_factor = 1.0 / (2.0 * zeta)
    dc_gain = TF_DC_GAIN

    return ComponentValues(
        resistance_ohm=resistance,
        inductance_henry=inductance_h,
        capacitance_farad=capacitance,
        target_freq_hz=target_freq_hz,
        omega_n=omega_target,
        zeta=zeta,
        q_factor=q_factor,
        dc_gain=dc_gain,
    )


def _format_value(value: float, unit: str) -> str:
    """Format a component value in SPICE notation (e.g. 100m, 33n, 1.36u)."""
    if value >= 1.0:
        return f"{value:.3f}{unit}"
    elif value >= 1e-3:
        return f"{value*1e3:.3f}m{unit}"
    elif value >= 1e-6:
        return f"{value*1e6:.3f}u{unit}"
    elif value >= 1e-9:
        return f"{value*1e9:.3f}n{unit}"
    elif value >= 1e-12:
        return f"{value*1e12:.3f}p{unit}"
    else:
        return f"{value:.6e}{unit}"


def _spice_value(value: float) -> str:
    """Format value in SPICE shorthand (100m, 33n, etc.)."""
    if value >= 1.0:
        return f"{value:.4g}"
    elif value >= 1e-3:
        return f"{value*1e3:.4g}m"
    elif value >= 1e-6:
        return f"{value*1e6:.4g}u"
    elif value >= 1e-9:
        return f"{value*1e9:.4g}n"
    elif value >= 1e-12:
        return f"{value*1e12:.4g}p"
    else:
        return f"{value:.4e}"


def generate_basic(target_freq_hz: float = FREQ_TESLA,
                   inductance_h: float = 100e-3,
                   excitation_amplitude: float = 1.0) -> SpiceNetlist:
    """Generate a basic series RLC netlist implementing H(s) = 9/(s²+3s+6).

    This is the minimum viable circuit — a single series RLC loop
    driven at the target frequency, with ζ = √6/4.
    """
    comp = compute_components(target_freq_hz, inductance_h)

    r_str = _spice_value(comp.resistance_ohm)
    l_str = _spice_value(comp.inductance_henry)
    c_str = _spice_value(comp.capacitance_farad)

    # SPICE netlist
    netlist = f"""\
* ═══════════════════════════════════════════════════════════
* S.E.I.F. Resonance Circuit — Series RLC
* H(s) = 9/(s² + 3s + 6),  ζ = √6/4 ≈ {comp.zeta:.6f}
* Target frequency: {target_freq_hz} Hz
* Q-factor: {comp.q_factor:.4f}
* DC gain: {comp.dc_gain}
*
* Component values derived from transfer function coefficients.
* This is formal-symbolic: standard control theory → RLC mapping.
* Protocol: github.com/and2carvalho/seif
* ═══════════════════════════════════════════════════════════

* === EXCITATION SOURCE ===
* AC sine at {target_freq_hz} Hz, {excitation_amplitude} Vpp
V1 input 0 SIN(0 {excitation_amplitude} {target_freq_hz}) AC {excitation_amplitude}

* === SERIES RLC (ζ = √6/4) ===
R1 input n1 {r_str}    ; Damping: R = 2ζωn·L = {comp.resistance_ohm:.4f} Ω
L1 n1 n2 {l_str}       ; Inductance: chosen = {comp.inductance_henry*1e3:.1f} mH
C1 n2 0 {c_str}        ; Capacitance: C = 1/(L·ωn²) = {comp.capacitance_farad:.4e} F

* === ANALYSIS ===
* AC sweep: 1 Hz to 100 kHz (logarithmic, 100 points/decade)
.AC DEC 100 1 100k

* Transient: 50 ms with 10 μs step (≈21 cycles at {target_freq_hz} Hz)
.TRAN 10u 50m

* === MEASUREMENTS ===
.MEAS AC f_peak WHEN MAG(V(n2)) = MAX
.MEAS AC bw_3db TRIG MAG(V(n2)) VAL=0.707*MAX RISE=1 TARG MAG(V(n2)) VAL=0.707*MAX FALL=1
.MEAS TRAN v_peak MAX V(n2)
.MEAS TRAN settle_time WHEN V(n2) < 1.02*{comp.dc_gain} RISE=1

.END
"""

    summary = (
        f"═══ SEIF RLC CIRCUIT — {target_freq_hz} Hz ═══\n"
        f"Transfer function: H(s) = 9/(s² + 3s + 6)\n"
        f"Damping ratio: ζ = √6/4 = {comp.zeta:.6f} ≈ φ⁻¹\n"
        f"Q-factor: {comp.q_factor:.4f}\n"
        f"\n"
        f"Components:\n"
        f"  R = {_format_value(comp.resistance_ohm, 'Ω'):<20} (damping)\n"
        f"  L = {_format_value(comp.inductance_henry, 'H'):<20} (energy storage)\n"
        f"  C = {_format_value(comp.capacitance_farad, 'F'):<20} (charge storage)\n"
        f"\n"
        f"Verification:\n"
        f"  ωn = 2π×{target_freq_hz} = {comp.omega_n:.2f} rad/s\n"
        f"  f_res = 1/(2π√LC) = {1/(2*math.pi*math.sqrt(comp.inductance_henry*comp.capacitance_farad)):.2f} Hz\n"
        f"  ζ = R/(2√(L/C)) = {comp.resistance_ohm/(2*math.sqrt(comp.inductance_henry/comp.capacitance_farad)):.6f}\n"
        f"  DC gain = 1/(ωn²·LC·R/L... ) = {comp.dc_gain}\n"
    )

    nodes = [
        SpiceNode("V1", 0.0, 0.5, "V", f"{excitation_amplitude}V@{target_freq_hz}Hz",
                  HarmonicPhase.SINGULARITY, 0),
        SpiceNode("R1", 0.25, 0.5, "R", _format_value(comp.resistance_ohm, "Ω"),
                  HarmonicPhase.DYNAMICS, 120),
        SpiceNode("L1", 0.5, 0.5, "L", _format_value(comp.inductance_henry, "H"),
                  HarmonicPhase.STABILIZATION, 240),
        SpiceNode("C1", 0.75, 0.5, "C", _format_value(comp.capacitance_farad, "F"),
                  HarmonicPhase.SINGULARITY, 360),
    ]

    return SpiceNetlist(
        title=f"SEIF RLC {target_freq_hz}Hz",
        nodes=nodes,
        netlist_text=netlist,
        component_summary=summary,
        target_freq_hz=target_freq_hz,
        components=comp,
    )


def generate_from_artifact(convergence_nodes: list[tuple[float, float]],
                           harmonic_score: float,
                           fractal_dimension: float,
                           target_freq_hz: float = FREQ_TESLA,
                           artifact_source: str = "unknown") -> SpiceNetlist:
    """Generate a multi-node SPICE netlist from artifact geometry.

    Maps the artifact's convergence nodes to RLC components:
      - Center node → voltage source (excitation)
      - Nodes at 0-120° → inductors (magnetic energy, like coil windings)
      - Nodes at 120-240° → capacitors (electric energy, like crystal faces)
      - Nodes at 240-360° → resistors (dissipation, like thermal paths)

    The total R, L, C values are distributed across nodes proportionally
    to their distance from center (φ-weighted).

    Stance label: This mapping is empirical-observational.
    The hypothesis is that artifact geometry encodes optimal component placement.
    Fabrication + measurement would be required to validate.
    """
    n_nodes = len(convergence_nodes)
    if n_nodes < 3:
        return generate_basic(target_freq_hz)

    comp = compute_components(target_freq_hz)

    # Find center of mass
    cx = sum(x for x, y in convergence_nodes) / n_nodes
    cy = sum(y for x, y in convergence_nodes) / n_nodes

    # Compute angle and distance from center for each node
    node_info = []
    for i, (x, y) in enumerate(convergence_nodes):
        dx, dy = x - cx, y - cy
        angle = math.degrees(math.atan2(dy, dx)) % 360
        dist = math.sqrt(dx**2 + dy**2)
        node_info.append((i, x, y, angle, dist))

    # Sort by angle
    node_info.sort(key=lambda n: n[3])

    # Assign component types by angular sector (3-fold: R, L, C)
    spice_nodes = []
    r_nodes, l_nodes, c_nodes = [], [], []

    # First node closest to center = source
    source_idx = min(range(n_nodes), key=lambda i: node_info[i][4])

    for idx, (i, x, y, angle, dist) in enumerate(node_info):
        if idx == source_idx:
            spice_nodes.append(SpiceNode(
                f"V1", x, y, "V",
                f"1V@{target_freq_hz}Hz",
                HarmonicPhase.SINGULARITY, angle,
            ))
            continue

        # 3-fold sector assignment
        sector = int(angle / 120)  # 0, 1, or 2
        if sector == 0:  # 0-120°: inductors
            l_nodes.append((idx, x, y, angle, dist))
        elif sector == 1:  # 120-240°: capacitors
            c_nodes.append((idx, x, y, angle, dist))
        else:  # 240-360°: resistors
            r_nodes.append((idx, x, y, angle, dist))

    # Distribute component values proportionally to distance from center
    def _distribute(total_val, nodes_list, comp_type, unit_char):
        if not nodes_list:
            return []
        total_dist = sum(d for _, _, _, _, d in nodes_list) or 1.0
        result = []
        for j, (idx, x, y, angle, dist) in enumerate(nodes_list):
            # φ-weighted distribution: further from center = larger value
            weight = dist / total_dist
            if comp_type == "R":
                # Resistors in series: divide total
                val = total_val * weight * len(nodes_list)
                phase = HarmonicPhase.DYNAMICS
            elif comp_type == "L":
                # Inductors in series: divide total
                val = total_val * weight * len(nodes_list)
                phase = HarmonicPhase.STABILIZATION
            else:  # C
                # Capacitors in parallel: multiply total
                val = total_val / (weight * len(nodes_list)) if weight > 0 else total_val
                phase = HarmonicPhase.SINGULARITY

            name = f"{comp_type}{j+1}"
            result.append(SpiceNode(
                name, x, y, comp_type,
                _format_value(val, unit_char),
                phase, angle,
            ))
        return result

    spice_nodes.extend(_distribute(comp.resistance_ohm, r_nodes, "R", "Ω"))
    spice_nodes.extend(_distribute(comp.inductance_henry, l_nodes, "L", "H"))
    spice_nodes.extend(_distribute(comp.capacitance_farad, c_nodes, "C", "F"))

    # Generate netlist text
    lines = [
        f"* ═══════════════════════════════════════════════════════════",
        f"* S.E.I.F. Artifact-Derived Circuit",
        f"* Source artifact: {artifact_source}",
        f"* Convergence nodes: {n_nodes} (detected by CV pipeline)",
        f"* Harmonic score: {harmonic_score:.3f} | Fractal D: {fractal_dimension:.3f}",
        f"* H(s) = 9/(s² + 3s + 6),  ζ = √6/4 ≈ {comp.zeta:.6f}",
        f"* Target frequency: {target_freq_hz} Hz",
        f"*",
        f"* Stance: artifact→circuit mapping is EMPIRICAL-OBSERVATIONAL.",
        f"* The geometry is measured. The component assignment is hypothesis.",
        f"* Fabrication + measurement required for validation.",
        f"* ═══════════════════════════════════════════════════════════",
        f"",
    ]

    # Source
    lines.append(f"* === EXCITATION SOURCE ===")
    lines.append(f"V1 input 0 SIN(0 1 {target_freq_hz}) AC 1")
    lines.append(f"")

    # Build series chain: V1 → R nodes → L nodes → C nodes → GND
    prev_net = "input"
    net_idx = 1

    lines.append(f"* === RESISTORS (sector 240°-360°, damping) ===")
    for node in [n for n in spice_nodes if n.component_type == "R"]:
        next_net = f"n{net_idx}"
        lines.append(f"{node.name} {prev_net} {next_net} {_spice_value(_parse_value(node.component_value))}    ; {node.component_value} @ {node.angle_deg:.0f}°")
        prev_net = next_net
        net_idx += 1

    lines.append(f"")
    lines.append(f"* === INDUCTORS (sector 0°-120°, energy storage) ===")
    for node in [n for n in spice_nodes if n.component_type == "L"]:
        next_net = f"n{net_idx}"
        lines.append(f"{node.name} {prev_net} {next_net} {_spice_value(_parse_value(node.component_value))}    ; {node.component_value} @ {node.angle_deg:.0f}°")
        prev_net = next_net
        net_idx += 1

    lines.append(f"")
    lines.append(f"* === CAPACITORS (sector 120°-240°, charge) ===")
    cap_nodes = [n for n in spice_nodes if n.component_type == "C"]
    for node in cap_nodes:
        # Capacitors to ground (parallel)
        lines.append(f"{node.name} {prev_net} 0 {_spice_value(_parse_value(node.component_value))}    ; {node.component_value} @ {node.angle_deg:.0f}°")

    lines.extend([
        f"",
        f"* === ANALYSIS ===",
        f".AC DEC 100 1 100k",
        f".TRAN 10u 50m",
        f"",
        f".MEAS AC f_peak WHEN MAG(V({prev_net})) = MAX",
        f".MEAS TRAN v_peak MAX V({prev_net})",
        f"",
        f".END",
    ])

    netlist_text = "\n".join(lines)

    summary = (
        f"═══ SEIF ARTIFACT CIRCUIT — {artifact_source} ═══\n"
        f"Nodes: {n_nodes} (source=1, R={len(r_nodes)}, L={len(l_nodes)}, C={len(c_nodes)})\n"
        f"Target: {target_freq_hz} Hz | ζ = {comp.zeta:.6f} | Q = {comp.q_factor:.3f}\n"
        f"Harmonic score: {harmonic_score:.3f} | Fractal D: {fractal_dimension:.3f}\n"
        f"\n"
        f"Base values (total):\n"
        f"  R = {_format_value(comp.resistance_ohm, 'Ω')}\n"
        f"  L = {_format_value(comp.inductance_henry, 'H')}\n"
        f"  C = {_format_value(comp.capacitance_farad, 'F')}\n"
    )

    return SpiceNetlist(
        title=f"SEIF Artifact Circuit — {artifact_source}",
        nodes=spice_nodes,
        netlist_text=netlist_text,
        component_summary=summary,
        target_freq_hz=target_freq_hz,
        components=comp,
        artifact_source=artifact_source,
    )


def _parse_value(formatted: str) -> float:
    """Parse a formatted value string back to float (e.g. '100.000mH' → 0.1)."""
    s = formatted.rstrip("ΩHFVHz@")
    s = s.strip()
    try:
        if s.endswith("p"):
            return float(s[:-1]) * 1e-12
        elif s.endswith("n"):
            return float(s[:-1]) * 1e-9
        elif s.endswith("u"):
            return float(s[:-1]) * 1e-6
        elif s.endswith("m"):
            return float(s[:-1]) * 1e-3
        else:
            return float(s)
    except ValueError:
        return 1.0


def save_netlist(netlist: SpiceNetlist, filename: Optional[str] = None) -> Path:
    """Save netlist to .cir file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in netlist.title)
        filename = f"{safe[:60]}.cir"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(netlist.netlist_text)
    return path


if __name__ == "__main__":
    # Demo: generate basic 432 Hz circuit
    print("═══ BASIC 432 Hz CIRCUIT ═══\n")
    basic = generate_basic(432)
    print(basic.component_summary)
    path = save_netlist(basic)
    print(f"\nSaved: {path}")
    print(f"\n{basic.netlist_text}")

    # Demo: generate from Giza parameters (438 Hz)
    print("\n═══ GIZA 438 Hz CIRCUIT ═══\n")
    giza = generate_basic(438)
    print(giza.component_summary)
    path2 = save_netlist(giza)
    print(f"Saved: {path2}")
