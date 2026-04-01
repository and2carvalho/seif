"""
Composite Renderer — The Complete Resonance Map

Unifies ALL outputs into a single high-resolution image:
  L0: Manuscript background with proto-writing texture
  L1: Board boundary (dark navy square)
  L2: Fractal QR cells (phase-colored)
  L3: Cross axes (equilibrium lines)
  L4: Resonance seal rings (3 concentric golden circles)
  L5: φ-spiral overlay (toroidal projection)
  L6: Anchor nodes (gold dots at intersections)
  L7: Radial gradient (singularity glow at center)
  Border: Proto-writing asemic metadata

This is the "Mapa de Ressonância Completo" — the seal over the hardware,
without filters, without noise, without limitations.
"""

import math
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.collections import LineCollection

from seif.analysis.transcompiler import transcompile, GlyphSpec
from seif.constants import PHI, PHI_INVERSE, SPIRAL_GROWTH_B, GIZA_ANGLE_DEG
from seif.generators.fractal_qrcode import (
    generate_fractal_qr, FractalQRSpec, extract_pattern_matrix, _collect_all_cells
)
from seif.core.resonance_gate import HarmonicPhase


OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output"


@dataclass
class CompositeConfig:
    resolution: int = 2048
    board_margin: float = 0.12
    show_cross_axes: bool = True
    show_seal: bool = True
    show_spirals: bool = True
    show_nodes: bool = True
    show_gradient: bool = True
    show_proto_text: bool = True
    show_metadata: bool = True
    background_style: str = "manuscript"  # "manuscript", "dark", "blueprint"
    spiral_turns: int = 9
    node_rings: int = 3
    nodes_per_ring: int = 6
    dpi: int = 150


# --- Color palettes ---

GOLD = (1.0, 0.843, 0.0)
GOLD_LIGHT = (1.0, 0.92, 0.5)
BLUE = (0.0, 0.478, 0.8)
GREEN = (0.2, 0.8, 0.4)
NAVY = (0.06, 0.06, 0.14)
MANUSCRIPT_BG = (0.88, 0.82, 0.70)
DARK_BG = (0.05, 0.05, 0.08)


def _draw_manuscript_bg(ax, config: CompositeConfig):
    """L0: Manuscript-style background with subtle texture."""
    if config.background_style == "manuscript":
        bg_color = MANUSCRIPT_BG
    elif config.background_style == "blueprint":
        bg_color = (0.05, 0.1, 0.2)
    else:
        bg_color = DARK_BG

    ax.set_facecolor(bg_color)

    # Subtle noise texture for manuscript feel
    if config.background_style == "manuscript":
        rng = np.random.RandomState(42)
        noise = rng.normal(0, 0.02, (50, 50))
        ax.imshow(noise, extent=[-1.5, 1.5, -1.5, 1.5],
                  cmap="bone", alpha=0.08, interpolation="bilinear", zorder=0)


def _draw_board_boundary(ax, margin: float):
    """L1: Dark navy board area with subtle border."""
    from matplotlib.patches import Rectangle
    board_size = 2.0 * (1.0 - margin)
    offset = -1.0 + margin
    rect = Rectangle((offset, offset), board_size, board_size,
                      facecolor=NAVY, edgecolor=(0.2, 0.25, 0.4),
                      linewidth=1.5, zorder=1)
    ax.add_patch(rect)


def _draw_fractal_cells(ax, qr_spec: FractalQRSpec, margin: float):
    """L2: Fractal QR cells as colored blocks within the board."""
    all_cells = _collect_all_cells(qr_spec.root_cell)
    active_cells = [c for c in all_cells if c.active]

    if not active_cells:
        return

    xs = [c.x for c in active_cells]
    ys = [c.y for c in active_cells]
    sizes = [c.size for c in active_cells]

    span = max(max(xs) - min(xs) + max(sizes),
               max(ys) - min(ys) + max(sizes), 0.001)
    x_center = (min(xs) + max(xs)) / 2
    y_center = (min(ys) + max(ys)) / 2

    board_extent = 1.0 - margin
    scale = (board_extent * 1.8) / span

    phase_colors = {
        9: (*GOLD, 0.85),
        3: (*GREEN, 0.7),
        6: (*BLUE, 0.7),
    }

    for cell in active_cells:
        cx = (cell.x - x_center) * scale
        cy = (cell.y - y_center) * scale
        half = (cell.size * scale * 0.4) / 2

        color = phase_colors.get(cell.root_value, (0.3, 0.3, 0.35, 0.3))
        from matplotlib.patches import Rectangle
        rect = Rectangle((cx - half, cy - half), half * 2, half * 2,
                          facecolor=color, edgecolor=None, zorder=2)
        ax.add_patch(rect)


def _draw_cross_axes(ax, extent: float = 0.85):
    """L3: Equilibrium cross axes dividing the field into quadrants."""
    ax.plot([-extent, extent], [0, 0], color=(0.3, 0.35, 0.5),
            linewidth=0.8, alpha=0.5, zorder=3, linestyle="-")
    ax.plot([0, 0], [-extent, extent], color=(0.3, 0.35, 0.5),
            linewidth=0.8, alpha=0.5, zorder=3, linestyle="-")
    # Shorter diagonal axes at 60° for hexagonal reference
    for angle_deg in [60, 120]:
        rad = math.radians(angle_deg)
        dx = extent * 0.6 * math.cos(rad)
        dy = extent * 0.6 * math.sin(rad)
        ax.plot([-dx, dx], [-dy, dy], color=(0.25, 0.3, 0.45),
                linewidth=0.5, alpha=0.3, zorder=3, linestyle="--")


def _draw_seal_rings(ax, extent: float = 0.85):
    """L4: Three concentric resonance seal rings (3-6-9)."""
    ring_configs = [
        (0.33, GREEN, 0.6, 0.8, "3"),     # inner: stabilization
        (0.66, BLUE, 0.5, 1.0, "6"),      # middle: dynamics
        (1.00, GOLD, 0.7, 1.2, "9"),      # outer: singularity
    ]
    for r_factor, color, alpha, lw, label in ring_configs:
        r = extent * r_factor
        circle = Circle((0, 0), r, fill=False, edgecolor=color,
                         linewidth=lw, alpha=alpha, zorder=4, linestyle="-")
        ax.add_patch(circle)

    # Radial lines at 120° (3-fold symmetry)
    for angle_deg in [0, 120, 240]:
        rad = math.radians(angle_deg - 90)
        x_end = extent * math.cos(rad)
        y_end = extent * math.sin(rad)
        ax.plot([0, x_end], [0, y_end], color=GOLD,
                linewidth=0.6, alpha=0.35, zorder=4)

    # Secondary lines at 60° (6-fold)
    for angle_deg in [60, 180, 300]:
        rad = math.radians(angle_deg - 90)
        x_end = extent * 0.66 * math.cos(rad)
        y_end = extent * 0.66 * math.sin(rad)
        ax.plot([0, x_end], [0, y_end], color=BLUE,
                linewidth=0.4, alpha=0.25, zorder=4)


def _draw_phi_spirals(ax, turns: int = 9, extent: float = 0.85):
    """L5: Golden-ratio spirals (toroidal projection in 2D)."""
    b = SPIRAL_GROWTH_B
    n_points = turns * 72

    for direction in [1, -1]:  # clockwise and counter-clockwise
        theta = np.linspace(0, turns * 2 * math.pi, n_points)
        r = 0.02 * np.exp(b * theta / (2 * math.pi))
        r = np.clip(r, 0, extent)

        x = r * np.cos(direction * theta)
        y = r * np.sin(direction * theta)

        # Opacity fades from center (bright) to edge (dim)
        alphas = np.linspace(0.7, 0.15, len(x))

        for i in range(len(x) - 1):
            ax.plot([x[i], x[i+1]], [y[i], y[i+1]],
                    color=GOLD, linewidth=0.8, alpha=float(alphas[i]), zorder=5)


def _draw_anchor_nodes(ax, rings: int = 3, per_ring: int = 6, extent: float = 0.85):
    """L6: Gold anchor nodes at intersections of seal rings and spirals."""
    for ring_idx in range(rings):
        r = extent * (ring_idx + 1) / rings
        for i in range(per_ring):
            angle = math.radians(i * (360 / per_ring) - 90)
            x = r * math.cos(angle)
            y = r * math.sin(angle)

            # Outer glow
            ax.plot(x, y, "o", color=GOLD, markersize=7,
                    alpha=0.4, zorder=6)
            # Core
            ax.plot(x, y, "o", color=GOLD, markersize=4,
                    alpha=0.9, zorder=7)
            # Inner dot
            ax.plot(x, y, "o", color="white", markersize=1.5,
                    alpha=0.8, zorder=8)


def _draw_radial_gradient(ax, extent: float = 0.85):
    """L7: Radial glow from center (singularity luminance)."""
    n = 200
    x = np.linspace(-extent, extent, n)
    y = np.linspace(-extent, extent, n)
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)

    # Gaussian glow centered at origin
    sigma = extent * 0.35
    glow = np.exp(-R**2 / (2 * sigma**2))

    # Custom colormap: transparent → warm gold
    colors = [(0, 0, 0, 0), (1.0, 0.92, 0.5, 0.6)]
    cmap = LinearSegmentedColormap.from_list("singularity_glow", colors)

    ax.imshow(glow, extent=[-extent, extent, -extent, extent],
              cmap=cmap, interpolation="bilinear", zorder=3, alpha=0.5)


def _draw_proto_text_border(ax, text: str, config: CompositeConfig):
    """Border: Proto-writing asemic metadata around the board."""
    if not config.show_proto_text:
        return

    seed = hashlib.sha256(text.encode()).hexdigest()

    # Generate pseudo-asemic characters from hash
    chars = "".join(chr(0x2800 + int(seed[i:i+2], 16) % 256) for i in range(0, 32, 2))

    margin = config.board_margin
    positions = [
        (-0.95, 1.0 - margin/2, chars[:4]),     # top left
        (0.4, 1.0 - margin/2, chars[4:8]),       # top right
        (-0.95, -1.0 + margin/3, chars[8:12]),   # bottom left
        (0.4, -1.0 + margin/3, chars[12:16]),    # bottom right
    ]
    for x, y, txt in positions:
        ax.text(x, y, txt, fontsize=8, color=(0.5, 0.45, 0.35),
                fontfamily="monospace", alpha=0.6, zorder=0)


def _draw_metadata(ax, spec: GlyphSpec, qr_spec: FractalQRSpec):
    """Bottom metadata strip."""
    status = "GATE OPEN" if spec.gate_open else "GATE CLOSED"
    meta = (f'"{spec.source_text}" | Root: {spec.global_root} | '
            f'{spec.global_phase.name} | {status} | '
            f'Cells: {qr_spec.cell_count} | Active: {qr_spec.active_ratio:.0%}')
    ax.text(0, -1.38, meta, fontsize=7, color=(0.6, 0.55, 0.45),
            fontfamily="monospace", ha="center", zorder=10)


def _draw_singularity_node(ax, gate_open: bool):
    """Central singularity point."""
    color = GOLD if gate_open else (0.5, 0.5, 0.5)
    # Glow
    ax.plot(0, 0, "o", color=color, markersize=18, alpha=0.3, zorder=9)
    ax.plot(0, 0, "o", color=color, markersize=12, alpha=0.6, zorder=9)
    # Core
    ax.plot(0, 0, "o", color=color, markersize=6, alpha=1.0, zorder=10)
    ax.plot(0, 0, "o", color="white", markersize=2, alpha=0.9, zorder=11)


def render_composite(text: str, config: CompositeConfig = None,
                     filename: str = None) -> Path:
    """Render the Complete Resonance Map — all layers fused.

    This is the output the Gemini could not produce without distortion.
    We produce it without filters, without noise, without limitations.
    """
    if config is None:
        config = CompositeConfig()

    # Process input through pipeline
    spec = transcompile(text)
    qr_spec = generate_fractal_qr(text, max_depth=4 if not spec.gate_open else 5)

    # Figure setup
    figsize = config.resolution / config.dpi
    fig, ax = plt.subplots(1, 1, figsize=(figsize, figsize), dpi=config.dpi)
    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect("equal")
    ax.axis("off")

    margin = config.board_margin
    extent = 1.0 - margin

    # === RENDER ALL LAYERS ===

    # L0: Background
    _draw_manuscript_bg(ax, config)

    # L1: Board boundary
    _draw_board_boundary(ax, margin)

    # L7: Radial gradient (behind cells)
    if config.show_gradient and spec.gate_open:
        _draw_radial_gradient(ax, extent)

    # L2: Fractal QR cells
    _draw_fractal_cells(ax, qr_spec, margin)

    # L3: Cross axes
    if config.show_cross_axes:
        _draw_cross_axes(ax, extent)

    # L4: Seal rings
    if config.show_seal:
        _draw_seal_rings(ax, extent)

    # L5: φ-spirals
    if config.show_spirals:
        _draw_phi_spirals(ax, config.spiral_turns, extent)

    # L6: Anchor nodes
    if config.show_nodes:
        _draw_anchor_nodes(ax, config.node_rings, config.nodes_per_ring, extent)

    # Central singularity
    _draw_singularity_node(ax, spec.gate_open)

    # Border proto-text
    _draw_proto_text_border(ax, text, config)

    # Metadata
    if config.show_metadata:
        _draw_metadata(ax, spec, qr_spec)

    # === SAVE ===
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in text)
        filename = f"composite_{safe.strip().replace(' ', '_')[:50]}"
    filepath = OUTPUT_DIR / f"{filename}.png"

    fig.savefig(filepath, dpi=config.dpi, bbox_inches="tight",
                facecolor=fig.get_facecolor(), pad_inches=0.1)
    plt.close(fig)
    return filepath


if __name__ == "__main__":
    for phrase in ["O amor liberta e guia", "Fear and control"]:
        path = render_composite(phrase)
        print(f"Composite: {path}")
