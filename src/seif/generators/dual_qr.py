"""
Dual-Layer QR Generator — Reversible Resonance Carrier

Design principle: IF IT CANNOT BE READ BACK, IT IS NOT COMMUNICATION.

Architecture:
  Layer 1: Standard QR (ISO 18004) — decodable payload (text + SEIF hash)
  Layer 2: Fractal QR (SEIF)       — harmonic overlay (visual coherence)

The Standard QR carries the recoverable payload: the original text and its
SEIF integrity hash. Any scanner can read it. The Fractal QR overlay renders
the harmonic state as a visual signature on top — beauty AND function.

When both layers are present in a scanned image, calibration becomes:
  payload_from_QR == original_text?     → integrity
  hash_from_QR    == computed_hash?     → authenticity
"""

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from seif.core.resonance_gate import digital_root, ascii_vibrational_sum, classify_phase, HarmonicPhase
from seif.constants import PHI_INVERSE
from seif.generators.fractal_qrcode import (
    generate_fractal_qr, FractalQRSpec, _collect_all_cells
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output"

# Phase color mapping (RGBA)
PHASE_COLORS = {
    9: (255, 215, 0, 180),     # gold — SINGULARITY
    3: (51, 204, 102, 150),    # green — STABILIZATION
    6: (0, 122, 204, 150),     # blue — DYNAMICS
}
ENTROPY_COLOR = (77, 77, 89, 80)


@dataclass
class DualQRSpec:
    """Complete dual-layer QR specification."""
    source_text: str
    seif_hash: str
    global_root: int
    global_phase: HarmonicPhase
    gate_open: bool
    payload: dict
    fractal_spec: FractalQRSpec
    image: Optional[Image.Image] = None


def _compute_seif_hash(text: str) -> str:
    """Compute SEIF integrity hash: SHA-256 of text + digital root metadata."""
    global_sum = ascii_vibrational_sum(text)
    global_root = digital_root(global_sum)
    phase = classify_phase(global_root)
    meta = f"{text}|root={global_root}|phase={phase.name}"
    return hashlib.sha256(meta.encode()).hexdigest()[:32]


def _build_payload(text: str, seif_hash: str, full: bool = False) -> dict:
    """Build the JSON payload embedded in the standard QR.

    Args:
        text: Input phrase.
        seif_hash: SEIF integrity hash.
        full: If True, include complete protocol data (v2 payload).
    """
    global_sum = ascii_vibrational_sum(text)
    global_root = digital_root(global_sum)
    phase = classify_phase(global_root)

    payload = {
        "protocol": "SEIF-SEED-v2" if full else "SEIF-QR-v1",
        "text": text,
        "root": global_root,
        "phase": phase.name,
        "gate": "OPEN" if phase != HarmonicPhase.ENTROPY else "CLOSED",
        "hash": seif_hash,
    }

    if full:
        from seif.constants import TF_ZETA, TF_ZETA_SQUARED, TF_DC_GAIN
        payload.update({
            "url": "https://github.com/and2carvalho/seif",
            "app": "https://seif-framework.streamlit.app",
            "tf": "H(s)=9/(s²+3s+6)",
            "zeta": round(TF_ZETA, 6),
            "zeta_sq": "3/8",
            "dc": "3/2",
            "unique": "b=3k,c=6k²",
            "f_peak": "216=6³",
            "spice": "0.01%",
            "k_crit": "3/4",
            "stance": "CONTEXT_NOT_COMMAND",
        })

    return payload


def _generate_standard_qr(payload: dict, box_size: int = 10,
                           border: int = 4) -> Image.Image:
    """Generate a standard ISO 18004 QR code from payload."""
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_H
    except ImportError:
        raise ImportError(
            "qrcode package required for Dual QR. Install: pip install qrcode[pil]"
        )

    payload_str = json.dumps(payload, separators=(",", ":"))

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,  # 30% error tolerance for overlay
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload_str)
    qr.make(fit=True)

    return qr.make_image(fill_color="black", back_color="white").convert("RGBA")


def _render_fractal_overlay(fractal_spec: FractalQRSpec,
                            size: tuple[int, int]) -> Image.Image:
    """Render fractal QR cells as a transparent RGBA overlay."""
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    pixels = np.array(overlay)

    all_cells = _collect_all_cells(fractal_spec.root_cell)
    active_cells = [c for c in all_cells if c.active]

    if not active_cells:
        return overlay

    xs = [c.x for c in active_cells]
    ys = [c.y for c in active_cells]
    sizes = [c.size for c in active_cells]

    x_min = min(xs) - max(sizes) * 0.5
    x_max = max(xs) + max(sizes) * 0.5
    y_min = min(ys) - max(sizes) * 0.5
    y_max = max(ys) + max(sizes) * 0.5

    span = max(x_max - x_min, y_max - y_min, 0.001)
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2

    w, h = size
    margin = 0.1  # keep within bounds
    usable = min(w, h) * (1 - 2 * margin)

    for cell in active_cells:
        cx = int(w / 2 + (cell.x - x_center) / span * usable)
        cy = int(h / 2 + (cell.y - y_center) / span * usable)
        half = max(1, int(cell.size / span * usable * 0.15))

        color = PHASE_COLORS.get(cell.root_value, ENTROPY_COLOR)

        y_start = max(0, cy - half)
        y_end = min(h, cy + half + 1)
        x_start = max(0, cx - half)
        x_end = min(w, cx + half + 1)

        pixels[y_start:y_end, x_start:x_end] = color

    return Image.fromarray(pixels, "RGBA")


def generate_dual_qr(text: str, max_depth: int = 4,
                     box_size: int = 10, border: int = 4,
                     full_payload: bool = False) -> DualQRSpec:
    """Generate a Dual-Layer QR: standard QR base + fractal harmonic overlay.

    The standard QR is always decodable by any scanner (30% error correction
    tolerates the fractal overlay). The fractal layer visualizes the harmonic
    state of the input — beauty over function, coherence over decoration.

    Args:
        text: Input phrase to encode.
        max_depth: Maximum fractal recursion depth.
        box_size: QR module size in pixels.
        border: QR quiet zone modules.

    Returns:
        DualQRSpec with composite image accessible via .image
    """
    seif_hash = _compute_seif_hash(text)
    payload = _build_payload(text, seif_hash, full=full_payload)
    fractal_spec = generate_fractal_qr(text, max_depth=max_depth)

    # Layer 1: Standard QR
    qr_image = _generate_standard_qr(payload, box_size=box_size, border=border)

    # Layer 2: Fractal overlay (same size as QR)
    overlay = _render_fractal_overlay(fractal_spec, qr_image.size)

    # Composite: QR base + fractal on top
    composite = Image.alpha_composite(qr_image, overlay)

    global_sum = ascii_vibrational_sum(text)
    global_root = digital_root(global_sum)
    global_phase = classify_phase(global_root)

    return DualQRSpec(
        source_text=text,
        seif_hash=seif_hash,
        global_root=global_root,
        global_phase=global_phase,
        gate_open=global_phase != HarmonicPhase.ENTROPY,
        payload=payload,
        fractal_spec=fractal_spec,
        image=composite,
    )


def save_dual_qr(spec: DualQRSpec, filename: Optional[str] = None) -> Path:
    """Save the dual-layer QR image to disk.

    Returns:
        Path to the saved PNG file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if filename is None:
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in spec.source_text)
        filename = f"dual_qr_{safe.strip().replace(' ', '_')[:50]}"

    filepath = OUTPUT_DIR / f"{filename}.png"
    spec.image.save(filepath)
    return filepath


def describe(spec: DualQRSpec) -> str:
    """Human-readable description of a Dual QR spec."""
    lines = [
        "═══ DUAL-LAYER QR CODE ═══",
        f'Text:        "{spec.source_text}"',
        f"Root:        {spec.global_root} → {spec.global_phase.name}",
        f"Gate:        {'OPEN' if spec.gate_open else 'CLOSED'}",
        f"SEIF Hash:   {spec.seif_hash}",
        f"Payload:     {json.dumps(spec.payload, indent=2)}",
        f"Fractal:     {spec.fractal_spec.cell_count} cells, "
        f"{spec.fractal_spec.active_ratio:.0%} active",
        f"Image:       {spec.image.size[0]}×{spec.image.size[1]} px" if spec.image else "Image: not rendered",
        "",
        "Layer 1: Standard QR (ISO 18004, ECC-H 30%)",
        "Layer 2: Fractal overlay (SEIF harmonic state)",
        "→ Any scanner reads Layer 1. Layer 2 is visual coherence proof.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    for phrase in ["O amor liberta e guia", "Enoch Seed", "Fear and control"]:
        spec = generate_dual_qr(phrase)
        path = save_dual_qr(spec)
        print(describe(spec))
        print(f"Saved: {path}\n")
