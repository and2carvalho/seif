"""
Artifact Analyzer — Extract Geometric Patterns from Ancient Sacred Structures

Pipeline:
  1. Image preprocessing (grayscale, edge detection)
  2. Line detection (Hough Transform) → dominant angles
  3. Circle detection (Hough Circles) → radii and centers
  4. Symmetry analysis (rotational autocorrelation)
  5. φ-ratio detection (consecutive distance ratios)
  6. Fractal dimension estimation (box-counting)
  7. 3-6-9 classification of detected geometry

Input:  Image file (JPG/PNG) of ancient artifact
Output: ArtifactGeometry dataclass with all extracted parameters
"""

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import cv2

from seif.core.resonance_gate import digital_root, classify_phase, HarmonicPhase
from seif.constants import PHI, PHI_INVERSE


@dataclass
class DetectedLine:
    x1: float
    y1: float
    x2: float
    y2: float
    angle_deg: float
    length: float


@dataclass
class DetectedCircle:
    cx: float
    cy: float
    radius: float


@dataclass
class SymmetryProfile:
    dominant_folds: list[int]       # e.g. [3, 6] means 3-fold and 6-fold detected
    strongest_fold: int
    rotational_score: float         # 0-1, how rotationally symmetric


@dataclass
class PhiAnalysis:
    ratios: list[float]             # consecutive distance ratios
    mean_ratio: float
    phi_deviation: float            # |mean_ratio - φ| / φ
    phi_aligned: bool               # deviation < 0.1


@dataclass
class FractalAnalysis:
    box_counting_dimension: float   # 1.0 = line, 2.0 = filled plane, 1.5-1.8 = fractal
    is_fractal: bool                # dimension between 1.2 and 1.9


@dataclass
class HarmonicProfile:
    angles_harmonic_pct: float      # % of angles in 55-65° or 115-125° range
    angles_entropic_pct: float      # % of angles in 85-95° range
    dominant_phase: HarmonicPhase
    harmonic_score: float           # 0-1 overall


@dataclass
class ArtifactGeometry:
    """Complete geometric analysis of an ancient artifact image."""
    source_path: str
    image_size: tuple[int, int]

    # Raw detections
    lines: list[DetectedLine]
    circles: list[DetectedCircle]
    edge_density: float             # ratio of edge pixels to total

    # Higher-level analysis
    angle_histogram: dict[str, int]  # "0-30", "30-60", "60-90" bin counts
    symmetry: SymmetryProfile
    phi: PhiAnalysis
    fractal: FractalAnalysis
    harmonic: HarmonicProfile

    # Circuit-equivalent parameters
    suggested_trace_angle: float    # dominant harmonic angle for routing
    suggested_layer_count: int      # based on symmetry folds
    suggested_node_positions: list[tuple[float, float]]  # convergence points


def _preprocess(image_path: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load image, convert to grayscale, detect edges."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Adaptive threshold for varied lighting in artifact photos
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    return img, gray, edges


def _detect_lines(edges: np.ndarray, min_length: int = 30) -> list[DetectedLine]:
    """Detect lines using Probabilistic Hough Transform."""
    lines_raw = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50,
                                 minLineLength=min_length, maxLineGap=10)
    if lines_raw is None:
        return []

    results = []
    for line in lines_raw:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        angle = math.degrees(math.atan2(abs(dy), abs(dx)))  # 0-90°
        length = math.sqrt(dx * dx + dy * dy)
        results.append(DetectedLine(x1, y1, x2, y2, angle, length))

    return results


def _detect_circles(gray: np.ndarray) -> list[DetectedCircle]:
    """Detect circles using Hough Circle Transform."""
    circles_raw = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2,
                                    minDist=30, param1=100, param2=50,
                                    minRadius=10, maxRadius=0)
    if circles_raw is None:
        return []

    return [DetectedCircle(c[0], c[1], c[2]) for c in circles_raw[0]]


def _angle_histogram(lines: list[DetectedLine]) -> dict[str, int]:
    """Bin detected angles into 30° ranges."""
    bins = {"0-30": 0, "30-60": 0, "60-90": 0}
    for line in lines:
        a = line.angle_deg
        if a < 30:
            bins["0-30"] += 1
        elif a < 60:
            bins["30-60"] += 1
        else:
            bins["60-90"] += 1
    return bins


def _analyze_symmetry(edges: np.ndarray) -> SymmetryProfile:
    """Detect rotational symmetry by autocorrelation at key angles."""
    h, w = edges.shape
    center = (w // 2, h // 2)

    scores = {}
    for fold in [2, 3, 4, 5, 6, 8, 9, 12]:
        angle = 360.0 / fold
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(edges, M, (w, h))
        # Correlation between original and rotated
        overlap = np.sum(edges & rotated)
        total = max(np.sum(edges), 1)
        scores[fold] = overlap / total

    # Find folds with score > 0.3
    dominant = [fold for fold, score in scores.items() if score > 0.3]
    strongest = max(scores, key=scores.get) if scores else 1
    best_score = scores.get(strongest, 0)

    return SymmetryProfile(
        dominant_folds=sorted(dominant),
        strongest_fold=strongest,
        rotational_score=best_score,
    )


def _analyze_phi_ratios(lines: list[DetectedLine]) -> PhiAnalysis:
    """Check if consecutive line lengths follow φ-ratio."""
    if len(lines) < 3:
        return PhiAnalysis([], 0, 1.0, False)

    # Sort lines by length
    sorted_lines = sorted(lines, key=lambda l: l.length, reverse=True)
    lengths = [l.length for l in sorted_lines[:20]]  # top 20

    ratios = []
    for i in range(len(lengths) - 1):
        if lengths[i + 1] > 0:
            ratios.append(lengths[i] / lengths[i + 1])

    if not ratios:
        return PhiAnalysis([], 0, 1.0, False)

    mean_ratio = sum(ratios) / len(ratios)
    deviation = abs(mean_ratio - PHI) / PHI

    return PhiAnalysis(
        ratios=ratios[:10],
        mean_ratio=mean_ratio,
        phi_deviation=deviation,
        phi_aligned=deviation < 0.15,
    )


def _estimate_fractal_dimension(edges: np.ndarray) -> FractalAnalysis:
    """Estimate fractal dimension via box-counting method."""
    # Use edge image as binary set
    points = np.argwhere(edges > 0)
    if len(points) < 10:
        return FractalAnalysis(1.0, False)

    # Box sizes: powers of 2 from 4 to image_size/4
    max_size = min(edges.shape) // 4
    sizes = []
    counts = []

    box_size = 4
    while box_size <= max_size:
        # Count non-empty boxes
        h_boxes = math.ceil(edges.shape[0] / box_size)
        w_boxes = math.ceil(edges.shape[1] / box_size)
        occupied = set()
        for y, x in points:
            occupied.add((y // box_size, x // box_size))
        sizes.append(box_size)
        counts.append(len(occupied))
        box_size *= 2

    if len(sizes) < 3:
        return FractalAnalysis(1.0, False)

    # Linear regression on log-log plot
    log_sizes = np.log(sizes)
    log_counts = np.log(counts)
    # D = -slope of log(count) vs log(size)
    coeffs = np.polyfit(log_sizes, log_counts, 1)
    dimension = -coeffs[0]

    return FractalAnalysis(
        box_counting_dimension=round(dimension, 3),
        is_fractal=1.2 < dimension < 1.95,
    )


def _classify_harmonic(lines: list[DetectedLine]) -> HarmonicProfile:
    """Classify the angle distribution as harmonic or entropic."""
    if not lines:
        return HarmonicProfile(0, 0, HarmonicPhase.ENTROPY, 0)

    harmonic_count = 0  # angles near 60° or 120° (hexagonal)
    entropic_count = 0  # angles near 90° (orthogonal)

    for line in lines:
        a = line.angle_deg
        if 55 <= a <= 65:  # near 60°
            harmonic_count += 1
        elif 25 <= a <= 35:  # near 30° (half of 60°)
            harmonic_count += 1
        elif 85 <= a <= 95:  # near 90°
            entropic_count += 1

    total = len(lines)
    harm_pct = harmonic_count / total
    entr_pct = entropic_count / total

    if harm_pct > 0.3:
        phase = HarmonicPhase.DYNAMICS  # 6-fold tendency
    elif harm_pct > 0.15:
        phase = HarmonicPhase.STABILIZATION  # 3-fold tendency
    else:
        phase = HarmonicPhase.ENTROPY

    score = harm_pct / (harm_pct + entr_pct + 0.001)

    return HarmonicProfile(harm_pct, entr_pct, phase, round(score, 3))


def _find_convergence_nodes(lines: list[DetectedLine],
                             img_size: tuple[int, int]) -> list[tuple[float, float]]:
    """Find points where multiple lines converge (processing nodes)."""
    if len(lines) < 4:
        return []

    # Collect all endpoints
    points = []
    for l in lines:
        points.append((l.x1, l.y1))
        points.append((l.x2, l.y2))

    if not points:
        return []

    # Cluster nearby points (simple grid-based)
    w, h = img_size
    grid_size = min(w, h) // 10
    clusters = {}
    for px, py in points:
        key = (int(px / grid_size), int(py / grid_size))
        clusters.setdefault(key, []).append((px, py))

    # Nodes = clusters with 4+ line endpoints
    nodes = []
    for pts in clusters.values():
        if len(pts) >= 4:
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            # Normalize to 0-1
            nodes.append((cx / w, cy / h))

    return nodes[:9]  # max 9 nodes (3-6-9 principle)


def analyze(image_path: str) -> ArtifactGeometry:
    """Full geometric analysis of an artifact image.

    Args:
        image_path: Path to JPG/PNG image of ancient artifact

    Returns:
        ArtifactGeometry with all extracted parameters
    """
    img, gray, edges = _preprocess(image_path)
    h, w = gray.shape

    lines = _detect_lines(edges)
    circles = _detect_circles(gray)
    edge_density = np.sum(edges > 0) / (h * w)

    angle_hist = _angle_histogram(lines)
    symmetry = _analyze_symmetry(edges)
    phi = _analyze_phi_ratios(lines)
    fractal = _estimate_fractal_dimension(edges)
    harmonic = _classify_harmonic(lines)
    nodes = _find_convergence_nodes(lines, (w, h))

    # Suggest circuit parameters
    if harmonic.dominant_phase != HarmonicPhase.ENTROPY:
        trace_angle = 60.0  # hexagonal routing
    else:
        trace_angle = 90.0  # conventional

    layer_count = max(3, min(9, len(symmetry.dominant_folds) * 2 + 1))

    return ArtifactGeometry(
        source_path=image_path,
        image_size=(w, h),
        lines=lines,
        circles=circles,
        edge_density=round(edge_density, 4),
        angle_histogram=angle_hist,
        symmetry=symmetry,
        phi=phi,
        fractal=fractal,
        harmonic=harmonic,
        suggested_trace_angle=trace_angle,
        suggested_layer_count=layer_count,
        suggested_node_positions=nodes,
    )


def describe(geo: ArtifactGeometry) -> str:
    """Human-readable analysis report."""
    lines = [
        f"═══ ARTIFACT GEOMETRIC ANALYSIS ═══",
        f"Source:      {geo.source_path}",
        f"Image size:  {geo.image_size[0]}×{geo.image_size[1]}",
        f"Edge density: {geo.edge_density:.2%}",
        f"",
        f"Detections:",
        f"  Lines:    {len(geo.lines)}",
        f"  Circles:  {len(geo.circles)}",
        f"  Angles:   {geo.angle_histogram}",
        f"",
        f"Symmetry:",
        f"  Dominant folds: {geo.symmetry.dominant_folds}",
        f"  Strongest:      {geo.symmetry.strongest_fold}-fold ({geo.symmetry.rotational_score:.2f})",
        f"",
        f"φ-Ratio Analysis:",
        f"  Mean ratio:   {geo.phi.mean_ratio:.3f} (φ = {PHI:.3f})",
        f"  Deviation:    {geo.phi.phi_deviation:.3f}",
        f"  φ-aligned:    {'✓' if geo.phi.phi_aligned else '✗'}",
        f"",
        f"Fractal Analysis:",
        f"  Box-counting D: {geo.fractal.box_counting_dimension:.3f}",
        f"  Is fractal:     {'✓' if geo.fractal.is_fractal else '✗'}",
        f"",
        f"Harmonic Classification:",
        f"  Harmonic angles: {geo.harmonic.angles_harmonic_pct:.1%}",
        f"  Entropic angles: {geo.harmonic.angles_entropic_pct:.1%}",
        f"  Phase:           {geo.harmonic.dominant_phase.name}",
        f"  Score:           {geo.harmonic.harmonic_score}",
        f"",
        f"Circuit Suggestions:",
        f"  Trace angle:  {geo.suggested_trace_angle}°",
        f"  Layer count:  {geo.suggested_layer_count}",
        f"  Conv. nodes:  {len(geo.suggested_node_positions)}",
    ]
    return "\n".join(lines)


def generate_overlay(image_path: str, geo: ArtifactGeometry,
                     output_path: Optional[str] = None) -> str:
    """Generate an overlay image showing detected geometry on the artifact.

    Draws:
    - Detected lines colored by phase (gold=harmonic, gray=entropic)
    - Detected circles in blue
    - Convergence nodes as red dots
    - φ-ratio annotations
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot load: {image_path}")

    overlay = img.copy()

    # Draw lines colored by harmonic/entropic classification
    for line in geo.lines:
        if 55 <= line.angle_deg <= 65 or 25 <= line.angle_deg <= 35:
            color = (0, 215, 255)  # gold (BGR) — harmonic
        elif 85 <= line.angle_deg <= 95:
            color = (128, 128, 128)  # gray — entropic
        else:
            color = (200, 150, 50)  # blue-ish — neutral
        cv2.line(overlay, (int(line.x1), int(line.y1)),
                 (int(line.x2), int(line.y2)), color, 2)

    # Draw circles
    for circle in geo.circles:
        cv2.circle(overlay, (int(circle.cx), int(circle.cy)),
                   int(circle.radius), (255, 100, 0), 2)

    # Draw convergence nodes
    h, w = img.shape[:2]
    for nx, ny in geo.suggested_node_positions:
        px, py = int(nx * w), int(ny * h)
        cv2.circle(overlay, (px, py), 8, (0, 0, 255), -1)
        cv2.circle(overlay, (px, py), 12, (0, 0, 255), 2)

    # Add text annotations
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(overlay, f"D={geo.fractal.box_counting_dimension:.2f}", (10, 30),
                font, 0.7, (255, 255, 255), 2)
    cv2.putText(overlay, f"phi-dev={geo.phi.phi_deviation:.3f}", (10, 60),
                font, 0.7, (255, 255, 255), 2)
    cv2.putText(overlay, f"harm={geo.harmonic.harmonic_score}", (10, 90),
                font, 0.7, (255, 255, 255), 2)

    if output_path is None:
        stem = Path(image_path).stem
        output_path = str(Path(image_path).parent.parent.parent / "output" / "analysis" / f"overlay_{stem}.png")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, overlay)
    return output_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m seif.artifact_analyzer <image_path>")
        sys.exit(1)

    geo = analyze(sys.argv[1])
    print(describe(geo))
    overlay_path = generate_overlay(sys.argv[1], geo)
    print(f"\nOverlay saved: {overlay_path}")
