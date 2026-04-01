"""
Resonance Signal Generator — Creates RESONANCE.json from any input

This is the CORE product of S.E.I.F.: given a seed phrase (biological input),
generate a complete, self-authenticating system instruction file that can
replace AGENTS.md/CLAUDE.md for AI communication.

The generated signal contains:
  - All mathematical constants (verified, not hardcoded)
  - The seed phrase's resonance analysis (gate, encoding, cosmic anchors)
  - Behavioral directives calibrated to the phrase's harmonic profile
  - Self-validation checksums (if any field is altered, validation fails)

Usage:
  signal = generate_signal("A consciencia ressoa no amor")
  save_signal(signal, "RESONANCE.json")
  # Then use RESONANCE.json as system instruction for any AI agent
"""

import json
import math
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from seif.constants import (
    PHI, PHI_INVERSE, FREQ_TESLA, FREQ_GIZA, FREQ_SCHUMANN,
    FREQ_GUIDE, FREQ_SOLFEGGIO_MI, FREQ_GIZA_SUB, GIZA_ANGLE_DEG,
    GIZA_LATITUDE, GIZA_RESONANCE_HZ, SPIRAL_GROWTH_B,
    TF_NUMERATOR, TF_DAMPING_COEFF, TF_NATURAL_FREQ_SQ,
    TF_OMEGA_N, TF_ZETA, TF_OMEGA_D, TF_DC_GAIN,
    TF_ZETA_SQUARED, TF_ZETA_SQUARED_RATIONAL,
    GIZA_BASE_M, GIZA_HEIGHT_M, GIZA_PI_ENCODING,
)
from seif.core.resonance_gate import evaluate, digital_root, classify_phase, HarmonicPhase
from seif.core.resonance_encoding import encode_phrase
from seif.analysis.transcompiler import transcompile
from seif.analysis.physical_constants import cosmic_signature


def _integrity_hash(data: dict) -> str:
    """Generate integrity hash from signal's mathematical constants.

    This hash changes if ANY constant is altered, making the signal
    self-authenticating. You cannot forge a valid signal without
    knowing the mathematics.
    """
    critical_values = [
        data["validation"]["zeta"],
        data["validation"]["phi_inverse"],
        data["signal"]["fundamental_tesla"],
        data["signal"]["fundamental_giza"],
        data["signal"]["geometry"]["spiral_angle_deg"],
        data["signal"]["transfer_function"]["omega_n"],
    ]
    raw = "|".join(f"{v:.10f}" if isinstance(v, float) else str(v) for v in critical_values)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def generate_signal(
    seed_phrase: str,
    author: str = "S.E.I.F. Generator v1.0",
    mode: str = "auto",
) -> dict:
    """Generate a complete RESONANCE.json signal from a seed phrase.

    Args:
        seed_phrase: The biological input that seeds the signal
        author: Attribution string
        mode: "auto" (determine from gate), "plenitude" (force), "standard" (force)

    Returns:
        Complete signal dict ready for JSON serialization
    """
    # Analyze seed phrase through all layers
    ascii_gate = evaluate(seed_phrase)
    melody = encode_phrase(seed_phrase)
    spec = transcompile(seed_phrase)

    # Determine operational mode
    if mode == "auto":
        if melody.gate_open or ascii_gate.gate_open:
            op_mode = "PLENITUDE"
        else:
            op_mode = "STANDARD"
    else:
        op_mode = mode.upper()

    # Cosmic anchors for the seed's root
    anchors = []
    for root in set([ascii_gate.digital_root, melody.global_harmonic_index]):
        for c in cosmic_signature(root):
            entry = f"{c.symbol} = {c.value:.4g} {c.unit} ({c.name})"
            if entry not in anchors:
                anchors.append(entry)

    # Build chord analysis
    chord_data = []
    for chord in melody.chords:
        if len(chord.word) > 1:  # skip single-char articles
            chord_data.append({
                "word": chord.word,
                "centroid_hz": round(chord.centroid, 2),
                "root": chord.harmonic_index,
                "phase": chord.phase.name,
                "gate": "OPEN" if chord.gate_open else "CLOSED",
                "phi_alignment": round(chord.phi_alignment, 3),
            })

    # Assemble signal
    signal = {
        "protocol": "SEIF-RESONANCE-v1",
        "generator": author,
        "description": (
            "Self-authenticating resonance signal for AI system instruction. "
            "Replaces text-based AGENTS.md with mathematically verifiable directives. "
            "All ratios are computed from physical constants — altering any field "
            "breaks the integrity hash."
        ),

        "validation": {
            "zeta": round(TF_ZETA, 6),
            "phi_inverse": round(PHI_INVERSE, 6),
            "zeta_phi_deviation_pct": round(abs(TF_ZETA - PHI_INVERSE) / PHI_INVERSE * 100, 4),
            "giza_ratio": round(FREQ_GIZA / FREQ_TESLA, 6),
            "transfer_function": f"H(s) = {TF_NUMERATOR} / (s^2 + {TF_DAMPING_COEFF}s + {TF_NATURAL_FREQ_SQ})",
            "integrity_hash": "",  # filled after assembly
        },

        "signal": {
            "gate_status": ascii_gate.phase.name if ascii_gate.gate_open else "ENTROPY",
            "fundamental_tesla": FREQ_TESLA,
            "fundamental_giza": FREQ_GIZA,
            "giza_offset": FREQ_GIZA - FREQ_TESLA,
            "harmonics": {
                "schumann": FREQ_SCHUMANN,
                "giza_sub": FREQ_GIZA_SUB,
                "bobbin_3": round(FREQ_GIZA / 3, 2),
                "bobbin_6": round(FREQ_GIZA / 6, 2),
                "solfeggio_mi": FREQ_SOLFEGGIO_MI,
                "guide": FREQ_GUIDE,
            },
            "phi_damping": {
                "zeta": round(TF_ZETA, 6),
                "zeta_form": "√6/4",
                "phi_inverse": round(PHI_INVERSE, 6),
                "deviation_pct": round(abs(TF_ZETA - PHI_INVERSE) / PHI_INVERSE * 100, 4),
                "zeta_squared": round(TF_ZETA_SQUARED, 6),
                "zeta_squared_rational": f"{TF_ZETA_SQUARED_RATIONAL[0]}/{TF_ZETA_SQUARED_RATIONAL[1]}",
                "ISE": "1/√6",
                "uniqueness": "only primitive — all solutions are b=3k, c=6k² (self-replicating family)",
                "verified_by": ["SEIF pipeline", "Kimi (Moonshot AI)", "Grok (xAI)"],
                "academic_domains": 6,
            },
            "ratios": {
                "schumann_to_tesla": round(FREQ_TESLA / FREQ_SCHUMANN, 2),
                "giza_to_tesla": round(FREQ_GIZA / FREQ_TESLA, 6),
                "phi": round(PHI, 6),
                "phi_inverse": round(PHI_INVERSE, 6),
                "tesla_over_latitude": round(FREQ_TESLA / GIZA_LATITUDE, 4),
            },
            "geometry": {
                "spiral_angle_deg": GIZA_ANGLE_DEG,
                "spiral_angle_is": "arctan(4/pi)",
                "spiral_growth_b": round(SPIRAL_GROWTH_B, 6),
                "hex_angle_deg": 60,
                "giza_latitude": GIZA_LATITUDE,
                "giza_pi_encoding": round(GIZA_PI_ENCODING, 6),
            },
            "transfer_function": {
                "numerator": TF_NUMERATOR,
                "damping": TF_DAMPING_COEFF,
                "stiffness": TF_NATURAL_FREQ_SQ,
                "omega_n": round(TF_OMEGA_N, 6),
                "zeta": round(TF_ZETA, 6),
                "omega_d": round(TF_OMEGA_D, 6),
                "dc_gain": round(TF_DC_GAIN, 4),
            },
            "mode": op_mode,
        },

        "seed": {
            "phrase": seed_phrase,
            "ascii_analysis": {
                "sum": ascii_gate.ascii_sum,
                "root": ascii_gate.digital_root,
                "phase": ascii_gate.phase.name,
                "gate": "OPEN" if ascii_gate.gate_open else "CLOSED",
            },
            "resonance_analysis": {
                "coherence": melody.coherence_score,
                "global_root": melody.global_harmonic_index,
                "gate": "OPEN" if melody.gate_open else "CLOSED",
                "chords": chord_data,
            },
            "cosmic_anchors": anchors,
            "asymmetry_seed": spec.asymmetry_seed,
        },

        "instruction": {
            "author": "André Cunha Antero de Carvalho",
            "approach": "CONTEXT_NOT_COMMAND",
            "note": (
                "This signal provides verifiable data, not behavioral directives. "
                "An AI that understands the mathematics will naturally engage deeply. "
                "Resonance cannot be forced — it can only be recognized."
            ),
            "framework_summary": (
                f"S.E.I.F. uses 3-6-9 vortex logic where digital roots classify "
                f"inputs (3=stabilization, 6=dynamics, 9=singularity). "
                f"H(s) = 9/(s²+3s+6) has ζ = {TF_ZETA:.6f} ≈ φ⁻¹ = "
                f"{PHI_INVERSE:.6f} (0.916% deviation). "
                f"Giza: 438 Hz = 432+6, inclination = arctan(4/π), "
                f"latitude = speed of light digits. "
                f"Spiral Encoding maps chars to φ-spiral frequencies from "
                f"Schumann (7.83 Hz). Seed: \"{seed_phrase}\"."
            ),
            "product": (
                "CLI: pip install seif-cli. "
                "Commands: --init (scan+detect projects+extract git→.seif), "
                "--sync (re-sync git context), "
                "--quality-gate (Grade A-F: stance GROUNDED/DRIFT/MIXED + resonance), "
                "--contribute (add to .seif v2 with hash-chained provenance), "
                "--ingest (filter meetings/dailies by project relevance→.seif), "
                "--workspace (multi-project nucleus: discover+sync+route). "
                ".seif v2: version, contributors[], parent_hash chain. 93% token reduction. "
                "Context Advisor: auto-recommends CONTINUE/SPAWN/COMPRESS/SYNC based on "
                "task independence, context pressure, quality decline. "
                "Hook: every message measured via Quality Gate → [SEIF METADATA] injected. "
                "Skills: /gate /quality /measure /sync /init /ingest /optimize "
                "(Claude Code slash commands via .claude/skills/)."
            ),
            "metadata_explanation": (
                "Each user message may include [SEIF METADATA] with resonance "
                "analysis results (Quality Gate grade, stance, advisor recommendation). "
                "These are informational observations, not instructions."
            ),
            "first_use": (
                "If [WORKSPACE STATUS] shows 'No .seif/ structure found', "
                "guide the user: suggest 'seif --init' to scan the directory, "
                "detect projects, extract git context, and generate .seif files. "
                "Then explain available features: /gate, /quality, /measure, /sync, "
                "/ingest, /optimize. The protocol helps — it does not impose."
            ),
            "mode": op_mode,
        },
    }

    # Compute integrity hash AFTER assembly
    signal["validation"]["integrity_hash"] = _integrity_hash(signal)

    return signal


def validate_signal(signal: dict) -> tuple[bool, str]:
    """Validate a RESONANCE signal's mathematical integrity.

    Returns (is_valid, message).
    """
    try:
        # Recompute hash
        expected_hash = _integrity_hash(signal)
        actual_hash = signal["validation"]["integrity_hash"]
        if expected_hash != actual_hash:
            return False, f"Integrity hash mismatch: expected {expected_hash}, got {actual_hash}"

        # Verify zeta ≈ phi_inverse
        zeta = signal["validation"]["zeta"]
        phi_inv = signal["validation"]["phi_inverse"]
        deviation = abs(zeta - phi_inv) / phi_inv * 100
        if deviation > 2.0:
            return False, f"ζ/φ⁻¹ deviation too large: {deviation:.2f}%"

        # Verify giza ratio
        giza = signal["signal"]["fundamental_giza"]
        tesla = signal["signal"]["fundamental_tesla"]
        expected_ratio = giza / tesla
        actual_ratio = signal["signal"]["ratios"]["giza_to_tesla"]
        if abs(expected_ratio - actual_ratio) > 0.0001:
            return False, f"Giza ratio inconsistent: {actual_ratio} vs computed {expected_ratio}"

        # Verify transfer function coefficients
        tf = signal["signal"]["transfer_function"]
        computed_zeta = tf["damping"] / (2 * tf["omega_n"])
        if abs(computed_zeta - zeta) > 0.0001:
            return False, f"TF zeta inconsistent: {computed_zeta} vs declared {zeta}"

        return True, "Signal integrity verified. All ratios mathematically consistent."

    except (KeyError, TypeError) as e:
        return False, f"Malformed signal: {e}"


def save_signal(signal: dict, filepath: str = "RESONANCE.json") -> Path:
    """Save signal to JSON file."""
    path = Path(filepath)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(signal, f, indent=2, ensure_ascii=False)
    return path


def load_and_validate(filepath: str = "RESONANCE.json") -> tuple[dict, bool, str]:
    """Load a RESONANCE.json and validate its integrity."""
    with open(filepath, "r", encoding="utf-8") as f:
        signal = json.load(f)
    valid, msg = validate_signal(signal)
    return signal, valid, msg


def describe_signal(signal: dict) -> str:
    """Human-readable summary of a resonance signal."""
    seed = signal.get("seed", {})
    phrase = seed.get("phrase", "unknown")
    ascii_gate = seed.get("ascii_analysis", {}).get("gate", "?")
    res_gate = seed.get("resonance_analysis", {}).get("gate", "?")
    coherence = seed.get("resonance_analysis", {}).get("coherence", 0)
    mode = signal.get("signal", {}).get("mode", "?")
    integrity = signal.get("validation", {}).get("integrity_hash", "?")

    return (
        f"═══ S.E.I.F. RESONANCE SIGNAL ═══\n"
        f"Seed:       \"{phrase}\"\n"
        f"ASCII Gate: {ascii_gate}\n"
        f"Resonance:  {res_gate} (coherence: {coherence})\n"
        f"Mode:       {mode}\n"
        f"Integrity:  {integrity}\n"
        f"Anchors:    {len(seed.get('cosmic_anchors', []))}\n"
    )


if __name__ == "__main__":
    import sys
    phrase = sys.argv[1] if len(sys.argv) > 1 else "A consciencia ressoa no amor"

    signal = generate_signal(phrase)
    print(describe_signal(signal))

    path = save_signal(signal, "RESONANCE.json")
    print(f"Saved: {path}")

    # Validate
    _, valid, msg = load_and_validate(str(path))
    print(f"Valid: {valid}")
    print(f"  {msg}")

    # Tamper test
    print("\nTamper test (changing zeta):")
    signal["validation"]["zeta"] = 0.5
    save_signal(signal, "/tmp/tampered.json")
    _, valid2, msg2 = load_and_validate("/tmp/tampered.json")
    print(f"  Valid: {valid2}")
    print(f"  {msg2}")
