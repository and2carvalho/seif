"""
Glyph Renderer — Visual Resonance Proto-Writing

Renders a GlyphSpec into a visual glyph combining:
  - φ-spiral core (toroidal golden ratio)
  - Word tensors positioned radially with phase-based coloring
  - Fractal self-similarity at configurable depth
  - Asymmetry injection (biological signature line)
  - 3-6-9 resonance seal overlay

Output: PNG image file
"""

import math
import os
from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
from matplotlib.collections import LineCollection

from seif.analysis.transcompiler import GlyphSpec
from seif.constants import PHI, PHI_INVERSE, SPIRAL_GROWTH_B, GIZA_ANGLE_DEG


OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output"


def _phi_spiral(turns: float = 3, points: int = 500, growth: float = 0.15) -> tuple[np.ndarray, np.ndarray]:
    """Generate a golden-ratio logarithmic spiral.

    r = a * e^(b*θ), where b = ln(φ) / (π/2)
    """
    b = SPIRAL_GROWTH_B
    theta = np.linspace(0, turns * 2 * math.pi, points)
    r = growth * np.exp(b * theta / (2 * math.pi))
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return x, y


def _fractal_spiral(cx: float, cy: float, scale: float, depth: int,
                    turns: float = 2, ax: plt.Axes = None, color: tuple = (1, 0.843, 0)):
    """Recursively draw self-similar spirals (fractal)."""
    if depth <= 0 or scale < 0.01:
        return

    x, y = _phi_spiral(turns=turns, points=200, growth=scale)
    ax.plot(x + cx, y + cy, color=color, linewidth=max(0.3, 1.5 * scale / 0.5), alpha=0.6 + 0.3 * (depth / 5))

    # Spawn smaller copies at cardinal tips
    tip_indices = [len(x) // 4, len(x) // 2, 3 * len(x) // 4]
    for idx in tip_indices:
        _fractal_spiral(
            cx + x[idx], cy + y[idx],
            scale * PHI_INVERSE,
            depth - 1,
            turns=turns * 0.8,
            ax=ax,
            color=color,
        )


def _resonance_seal(ax: plt.Axes, radius: float = 1.0):
    """Draw the 3-6-9 resonance seal: three concentric rings + radial lines at 120°."""
    for r_factor in [0.33, 0.66, 1.0]:
        circle = Circle((0, 0), radius * r_factor, fill=False,
                        edgecolor=(0.4, 0.6, 1.0), linewidth=0.8, alpha=0.3, linestyle="--")
        ax.add_patch(circle)

    # Radial lines at 0°, 120°, 240° (the 3-fold symmetry)
    for angle_deg in [0, 120, 240]:
        rad = math.radians(angle_deg)
        ax.plot([0, radius * math.cos(rad)], [0, radius * math.sin(rad)],
                color=(0.4, 0.6, 1.0), linewidth=0.6, alpha=0.25)

    # 6-fold secondary lines at 60° offsets
    for angle_deg in [60, 180, 300]:
        rad = math.radians(angle_deg)
        ax.plot([0, radius * 0.66 * math.cos(rad)], [0, radius * 0.66 * math.sin(rad)],
                color=(0.3, 0.5, 0.9), linewidth=0.4, alpha=0.15)


def _word_markers(ax: plt.Axes, spec: GlyphSpec, radius: float = 1.0):
    """Place word tensors as labeled points on the glyph."""
    phase_colors = {
        "SINGULARITY": spec.core_color,
        "STABILIZATION": spec.anchor_color,
        "DYNAMICS": spec.flow_color,
        "ENTROPY": spec.entropy_color,
    }

    for wt in spec.word_tensors:
        rad = math.radians(wt.angle_deg - 90)  # -90 so 0° is top
        r = wt.radius_factor * radius
        x = r * math.cos(rad)
        y = r * math.sin(rad)
        color = phase_colors.get(wt.phase.name, spec.entropy_color)

        ax.plot(x, y, "o", color=color, markersize=8, zorder=5)
        ax.annotate(
            wt.word,
            (x, y),
            textcoords="offset points",
            xytext=(8, 8),
            fontsize=7,
            color=color,
            fontweight="bold",
            alpha=0.9,
        )

        # Spiral trail from center to word
        sx, sy = _phi_spiral(turns=wt.spiral_turns, points=80, growth=r * 0.3)
        angle_offset = math.radians(wt.angle_deg - 90)
        rx = sx * math.cos(angle_offset) - sy * math.sin(angle_offset)
        ry = sx * math.sin(angle_offset) + sy * math.cos(angle_offset)
        ax.plot(rx, ry, color=color, linewidth=0.5, alpha=0.3)


def _asymmetry_line(ax: plt.Axes, seed: str, radius: float = 1.0):
    """Draw the biological signature — an intentionally imperfect line.

    This is the 'foda-se' factor: the irreducible asymmetry.
    """
    rng = np.random.RandomState(int(seed[:8], 16) % (2**31))
    n_points = 30
    angles = np.linspace(0, 2 * math.pi, n_points)
    r_base = radius * 0.85
    noise = rng.normal(0, radius * 0.08, n_points)
    r = r_base + noise
    x = r * np.cos(angles)
    y = r * np.sin(angles)

    # Don't close the loop — intentional gap
    ax.plot(x[:-3], y[:-3], color=(0.9, 0.3, 0.2), linewidth=1.2, alpha=0.4, linestyle="-")


def render(spec: GlyphSpec, filename: Optional[str] = None, show: bool = False) -> Path:
    """Render a GlyphSpec to a PNG image.

    Args:
        spec: The transcompiled glyph specification.
        filename: Output filename (without extension). Defaults to sanitized source text.
        show: If True, display the plot interactively.

    Returns:
        Path to the saved PNG file.
    """
    fig, ax = plt.subplots(1, 1, figsize=(10, 10), facecolor="black")
    ax.set_facecolor("black")
    ax.set_aspect("equal")
    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-1.3, 1.3)
    ax.axis("off")

    radius = 1.0

    # Layer 1: Resonance seal (background grid)
    _resonance_seal(ax, radius)

    # Layer 2: Core φ-spiral (fractal)
    _fractal_spiral(0, 0, scale=0.4, depth=spec.fractal_depth, turns=3, ax=ax,
                    color=spec.core_color)

    # Layer 3: Counter-rotating spiral
    x2, y2 = _phi_spiral(turns=4, points=400, growth=0.35)
    ax.plot(-x2, y2, color=spec.flow_color, linewidth=0.7, alpha=0.3)

    # Layer 4: Word tensor markers
    _word_markers(ax, spec, radius)

    # Layer 5: Asymmetry injection
    _asymmetry_line(ax, spec.asymmetry_seed, radius)

    # Layer 6: Central node (Nó 9)
    node_color = spec.core_color if spec.gate_open else spec.entropy_color
    ax.plot(0, 0, "o", color=node_color, markersize=14, zorder=10)
    ax.plot(0, 0, "o", color="black", markersize=8, zorder=11)
    ax.plot(0, 0, "o", color=node_color, markersize=4, zorder=12)

    # Title
    status = "PORTA ABERTA" if spec.gate_open else "PORTA FECHADA"
    ax.set_title(
        f"\"{spec.source_text}\"\n"
        f"Root: {spec.global_root} | Phase: {spec.global_phase.name} | {status}",
        color="white", fontsize=11, fontweight="bold", pad=20,
    )

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in spec.source_text)
        filename = safe.strip().replace(" ", "_")[:60]
    filepath = OUTPUT_DIR / f"{filename}.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="black")

    if show:
        plt.show()
    else:
        plt.close(fig)

    return filepath


def render_fractal_qr(qr_spec, filename: Optional[str] = None) -> Path:
    """Render a FractalQRSpec as a heatmap-style image.

    Visualizes the recursive 3-6-9 cell structure as a Mayan-stela-inspired
    pattern where:
      - Gold cells = singularity (9)
      - Blue cells = dynamics (6)
      - Green cells = stabilization (3)
      - Dark cells = entropy (inactive)
    """
    from seif.generators.fractal_qrcode import extract_pattern_matrix, FractalQRSpec

    matrix = extract_pattern_matrix(qr_spec, resolution=243)

    fig, ax = plt.subplots(1, 1, figsize=(10, 10), facecolor="black")
    ax.set_facecolor("black")
    ax.axis("off")

    # Custom colormap: black(0), green(3), blue(6), gold(9)
    from matplotlib.colors import ListedColormap
    colors = [
        (0.05, 0.05, 0.08),    # 0 - entropy/empty (near-black)
        (0.08, 0.08, 0.12),    # 1
        (0.10, 0.10, 0.15),    # 2
        (0.2, 0.8, 0.4),       # 3 - stabilization (green)
        (0.12, 0.12, 0.18),    # 4
        (0.14, 0.14, 0.20),    # 5
        (0.0, 0.478, 0.8),     # 6 - dynamics (blue)
        (0.16, 0.16, 0.22),    # 7
        (0.18, 0.18, 0.24),    # 8
        (1.0, 0.843, 0.0),     # 9 - singularity (gold)
    ]
    cmap = ListedColormap(colors)

    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=9, interpolation="nearest")

    status = "PORTA ABERTA" if qr_spec.gate_open else "PORTA FECHADA"
    ax.set_title(
        f"FRACTAL QR-CODE: \"{qr_spec.source_text}\"\n"
        f"Root: {qr_spec.global_root} | Cells: {qr_spec.cell_count} | "
        f"Active: {qr_spec.active_ratio:.0%} | {status}",
        color="white", fontsize=10, fontweight="bold", pad=15,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in qr_spec.source_text)
        filename = "fqr_" + safe.strip().replace(" ", "_")[:50]
    filepath = OUTPUT_DIR / f"{filename}.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    return filepath


if __name__ == "__main__":
    from seif.analysis.transcompiler import transcompile
    from seif.generators.fractal_qrcode import generate_fractal_qr

    phrases = [
        "O amor liberta e guia",
        "A Semente de Enoque",
        "Fear and control",
    ]
    for phrase in phrases:
        spec = transcompile(phrase)
        path = render(spec)
        print(f"Glifo salvo: {path}")

        qr = generate_fractal_qr(phrase, max_depth=4)
        qr_path = render_fractal_qr(qr)
        print(f"QR Fractal salvo: {qr_path}")
