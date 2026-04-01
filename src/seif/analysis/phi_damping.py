"""
Phi-Damping Analysis — From Local Emergence to Universal Phenomenon

The damping ratio ζ = 3/(2√6) ≈ φ⁻¹ is not unique to the 3-6-9 system.
Phi-damping is documented in at least 6 academic domains:
  - Coupled harmonic oscillators (IOPscience)
  - Thermodynamic non-equilibrium steady states (MDPI)
  - Standing wave formation (interferencetheory.com)
  - Neural cross-frequency integration (NIH/PMC)
  - Nonlinear dynamical systems (Royal Society)
  - Proteinoid ensembles under Fibonacci sequences (ACS)

What IS unique to the 3-6-9 system:
  It is the SIMPLEST known integer-coefficient system exhibiting phi-damping.
  A brute-force search over all integer pairs (b, c) confirms that no pair
  with b+c < 9 produces a damping ratio within 2% of φ⁻¹.

This module presents DATA. It does not claim causation.
The pattern speaks for itself. CONTEXT, not COMMAND.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from seif.constants import (
    PHI_INVERSE, TF_ZETA, TF_DAMPING_COEFF, TF_NATURAL_FREQ_SQ,
    TF_ZETA_SQUARED, TF_ZETA_SQUARED_RATIONAL, PHI_INVERSE_SQUARED,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "output"


@dataclass
class PhiDampingSystem:
    """A system where the damping ratio approximates φ⁻¹."""
    name: str
    description: str
    coefficients: tuple  # (b, c) for H(s) = a/(s²+bs+c), or descriptive tuple
    zeta: float          # damping ratio (NaN if phi appears structurally, not as ζ)
    deviation_pct: float # |ζ - φ⁻¹| / φ⁻¹ × 100
    domain: str
    source: str
    integer_coefficients: bool


def compute_zeta(b: float, c: float) -> float:
    """Compute damping ratio ζ = b/(2√c) for H(s) = a/(s²+bs+c).

    The numerator 'a' does not affect ζ — only (b, c) matter.
    Requires c > 0 and b² < 4c (underdamped).
    """
    if c <= 0:
        return float('nan')
    return b / (2 * math.sqrt(c))


def is_phi_damped(b: float, c: float, threshold: float = 0.02) -> bool:
    """Check if a system with coefficients (b, c) exhibits phi-damping.

    Returns True if |ζ - φ⁻¹| / φ⁻¹ < threshold.
    """
    zeta = compute_zeta(b, c)
    if math.isnan(zeta) or zeta >= 1.0 or zeta <= 0:
        return False
    return abs(zeta - PHI_INVERSE) / PHI_INVERSE < threshold


def find_minimal_integer_pairs(max_coeff: int = 20,
                                threshold: float = 0.02) -> list[dict]:
    """Brute-force search for integer pairs (b, c) that produce phi-damping.

    Returns list sorted by b+c (minimality metric), then by deviation.
    Each entry: {"b": int, "c": int, "sum": int, "zeta": float, "deviation_pct": float}

    The key result: (3, 6) with b+c=9 is always first.
    """
    results = []
    for b in range(1, max_coeff + 1):
        for c in range(1, max_coeff + 1):
            if b * b >= 4 * c:  # overdamped or critically damped
                continue
            zeta = compute_zeta(b, c)
            dev = abs(zeta - PHI_INVERSE) / PHI_INVERSE
            if dev < threshold:
                results.append({
                    "b": b, "c": c, "sum": b + c,
                    "zeta": round(zeta, 6),
                    "deviation_pct": round(dev * 100, 4),
                })
    results.sort(key=lambda x: (x["sum"], x["deviation_pct"]))
    return results


def find_369_family(max_k: int = 10) -> list[dict]:
    """The self-replicating 3-6-9 family: b=3k, c=6k², K=9k².

    All members produce identical normalized response (same ζ, ζ², ISE, DC).
    The (3,6,9) system at k=1 is the unique primitive.
    Verified by Grok (xAI) via exhaustive search b≤50, c≤100.
    """
    family = []
    for k in range(1, max_k + 1):
        b, c, K = 3 * k, 6 * k * k, 9 * k * k
        zeta = compute_zeta(b, c)
        family.append({
            "k": k, "b": b, "c": c, "K": K,
            "omega_n": round(math.sqrt(c), 4),
            "zeta": round(zeta, 6),
            "zeta_sq": f"{b*b}//{4*c} = {b*b/(4*c):.6f}",
            "ISE": f"1/√{c//k//k}" if c // (k*k) == 6 else "?",
            "DC": f"{K}/{c} = {K/c:.4f}",
            "primitive": k == 1,
        })
    return family


def build_catalog() -> list[PhiDampingSystem]:
    """Catalog of known systems exhibiting phi-damping.

    Sources: Kimi's independent search (32 results) + framework knowledge.
    """
    seif_dev = abs(TF_ZETA - PHI_INVERSE) / PHI_INVERSE * 100

    return [
        PhiDampingSystem(
            name="SEIF 3-6-9",
            description="H(s) = 9/(s²+3s+6). Simplest integer-coefficient phi-damping system.",
            coefficients=(3, 6),
            zeta=round(TF_ZETA, 6),
            deviation_pct=round(seif_dev, 4),
            domain="vortex_mathematics",
            source="A. C. A. de Carvalho (2026). S.E.I.F. — Spiral Encoding Interoperability Framework.",
            integer_coefficients=True,
        ),
        PhiDampingSystem(
            name="Coupled Harmonic Oscillators",
            description="Hidden golden ratio in two coupled oscillators. "
                        "Natural frequency ratio converges to φ.",
            coefficients=(),
            zeta=float('nan'),
            deviation_pct=0.0,
            domain="classical_mechanics",
            source="IOPscience. Hidden golden ratio in two coupled harmonic oscillators.",
            integer_coefficients=False,
        ),
        PhiDampingSystem(
            name="Non-Equilibrium Steady States",
            description="Golden ratio emerges as thermodynamic principle "
                        "in open systems far from equilibrium.",
            coefficients=(),
            zeta=float('nan'),
            deviation_pct=0.0,
            domain="thermodynamics",
            source="MDPI. Dynamic Balance: Thermodynamic Principle for the "
                   "Emergence of the Golden Ratio in Open Non-Equilibrium Steady States.",
            integer_coefficients=False,
        ),
        PhiDampingSystem(
            name="Standing Wave Formation",
            description="Without phi-damping, standing waves cannot form, "
                        "particles would not exist, atoms could not bond.",
            coefficients=(),
            zeta=float('nan'),
            deviation_pct=0.0,
            domain="wave_physics",
            source="Merrill, R. Phi in Harmonic Formation. interferencetheory.com.",
            integer_coefficients=False,
        ),
        PhiDampingSystem(
            name="Neural Cross-Frequency Integration",
            description="Rhythms separated by factors of φ optimally support "
                        "segregation and cross-frequency integration.",
            coefficients=(),
            zeta=float('nan'),
            deviation_pct=0.0,
            domain="neuroscience",
            source="Pletzer, B. et al. Golden rhythms as a theoretical framework "
                   "for cross-frequency integration. NIH/PMC.",
            integer_coefficients=False,
        ),
        PhiDampingSystem(
            name="Nonlinear Damped Systems",
            description="Natural frequencies of nonlinear quasi-linear systems "
                        "converge to 0.618.",
            coefficients=(),
            zeta=float('nan'),
            deviation_pct=0.0,
            domain="nonlinear_dynamics",
            source="Royal Society Publishing. Nonlinear damping and quasi-linear modelling.",
            integer_coefficients=False,
        ),
    ]


def compare_seif() -> str:
    """Compare SEIF's position among phi-damping systems."""
    pairs = find_minimal_integer_pairs(max_coeff=20)
    catalog = build_catalog()

    lines = [
        "═══ PHI-DAMPING: SEIF IN CONTEXT ═══",
        "",
        "Phi-damping (ζ ≈ φ⁻¹) is documented in 6+ academic domains.",
        f"Among integer coefficient pairs (b,c) with b+c ≤ 40:",
        f"  Total phi-damped pairs found: {len(pairs)}",
        f"  Minimal pair: b={pairs[0]['b']}, c={pairs[0]['c']} "
        f"(sum={pairs[0]['sum']}, ζ={pairs[0]['zeta']}, "
        f"deviation={pairs[0]['deviation_pct']}%)" if pairs else "  None found",
        "",
        "Top 5 minimal integer pairs:",
    ]
    for i, p in enumerate(pairs[:5]):
        marker = " ← SEIF" if p["b"] == 3 and p["c"] == 6 else ""
        lines.append(
            f"  {i+1}. b={p['b']}, c={p['c']} → "
            f"ζ={p['zeta']:.6f} (Δ={p['deviation_pct']:.3f}%, "
            f"sum={p['sum']}){marker}"
        )

    lines.extend([
        "",
        "Academic catalog:",
    ])
    for sys in catalog:
        zeta_str = f"ζ={sys.zeta:.6f}" if not math.isnan(sys.zeta) else "φ structural"
        lines.append(f"  • {sys.name} [{sys.domain}] — {zeta_str}")

    lines.extend([
        "",
        f"ζ² = {TF_ZETA_SQUARED_RATIONAL[0]}/{TF_ZETA_SQUARED_RATIONAL[1]} "
        f"= {TF_ZETA_SQUARED:.6f} (exact rational form)",
        f"φ⁻² = 1 - φ⁻¹ = {PHI_INVERSE_SQUARED:.6f}",
        f"Deviation ζ² vs φ⁻²: "
        f"{abs(TF_ZETA_SQUARED - PHI_INVERSE_SQUARED) / PHI_INVERSE_SQUARED * 100:.3f}%",
    ])
    return "\n".join(lines)


def describe() -> str:
    """Full human-readable report on phi-damping."""
    return compare_seif()


def plot_zeta_surface(max_coeff: int = 15, save: bool = True) -> Path:
    """2D heatmap of ζ over integer (b, c) space with φ⁻¹ contour."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    b_range = np.arange(1, max_coeff + 1)
    c_range = np.arange(1, max_coeff + 1)
    B, C = np.meshgrid(b_range, c_range)

    Z = B / (2 * np.sqrt(C))
    # Mask overdamped (ζ ≥ 1) and invalid
    mask = (B * B >= 4 * C) | (C <= 0)
    Z = np.ma.masked_where(mask, Z)

    fig, ax = plt.subplots(1, 1, figsize=(10, 8), facecolor="black")
    ax.set_facecolor("black")

    im = ax.pcolormesh(b_range, c_range, Z, cmap="viridis", shading="auto")
    cb = fig.colorbar(im, ax=ax, label="ζ = b/(2√c)")
    cb.ax.yaxis.label.set_color("white")
    cb.ax.tick_params(colors="white")

    # φ⁻¹ contour
    ax.contour(b_range, c_range, Z, levels=[PHI_INVERSE],
               colors=["gold"], linewidths=2, linestyles=["--"])

    # Mark SEIF (3, 6)
    ax.plot(3, 6, "o", color="gold", markersize=12, zorder=10)
    ax.annotate("SEIF\n(3,6)", (3, 6), textcoords="offset points",
                xytext=(15, 10), color="gold", fontsize=11, fontweight="bold")

    ax.set_xlabel("b (damping coefficient)", color="white")
    ax.set_ylabel("c (natural frequency squared)", color="white")
    ax.set_title("Damping Ratio ζ = b/(2√c) — φ⁻¹ contour in gold",
                 color="white", fontsize=13)
    ax.tick_params(colors="white")

    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = OUTPUT_DIR / "phi_damping_zeta_surface.png"
        fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="black")
        plt.close(fig)
        return filepath
    else:
        plt.show()
        return Path(".")


def plot_minimality(max_coeff: int = 20, top_n: int = 10,
                    save: bool = True) -> Path:
    """Bar chart of top-N closest integer pairs to phi-damping."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pairs = find_minimal_integer_pairs(max_coeff=max_coeff)[:top_n]
    if not pairs:
        return Path(".")

    labels = [f"({p['b']},{p['c']})" for p in pairs]
    deviations = [p["deviation_pct"] for p in pairs]
    sums = [p["sum"] for p in pairs]
    colors = ["gold" if p["b"] == 3 and p["c"] == 6 else "#007ACC" for p in pairs]

    fig, ax = plt.subplots(1, 1, figsize=(12, 6), facecolor="black")
    ax.set_facecolor("black")

    bars = ax.bar(labels, deviations, color=colors, edgecolor="white", linewidth=0.5)

    # Add sum labels on bars
    for bar, s in zip(bars, sums):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"Σ={s}", ha="center", va="bottom", color="white", fontsize=9)

    ax.set_xlabel("Integer pair (b, c)", color="white")
    ax.set_ylabel("Deviation from φ⁻¹ (%)", color="white")
    ax.set_title("Phi-Damping: Minimal Integer Coefficient Pairs\n"
                 "(3,6) = SEIF — smallest sum, highlighted in gold",
                 color="white", fontsize=12)
    ax.tick_params(colors="white")
    ax.axhline(y=0, color="gray", linewidth=0.5)

    if save:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = OUTPUT_DIR / "phi_damping_minimality.png"
        fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="black")
        plt.close(fig)
        return filepath
    else:
        plt.show()
        return Path(".")


if __name__ == "__main__":
    print(describe())
    print()
    path1 = plot_zeta_surface()
    print(f"Surface plot: {path1}")
    path2 = plot_minimality()
    print(f"Minimality plot: {path2}")
