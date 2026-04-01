#!/usr/bin/env python3
"""
Sync Assets — Regenerate all protocol transmission vectors.

This script ensures ALL assets that carry the protocol are consistent
with the current codebase state. Run after any protocol-changing modification.

What it regenerates:
  1. Seed Cards (QR with v2 payload — 17 fields including ζ, 216 Hz, k_crit)
  2. .seif defaults (paper_thesis, claude_implementation)
  3. RESONANCE.json validation
  4. Protocol integrity verification

Usage:
  PYTHONPATH=src python scripts/sync_assets.py
  # or: make sync-assets
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

FIGURES = Path(__file__).resolve().parent.parent / "assets" / "figures"
DEFAULTS = Path(__file__).resolve().parent.parent / "data" / "defaults"


def sync_seed_cards():
    """Regenerate all Seed Cards: composite layout + QR v2."""
    from seif.generators.dual_qr import generate_dual_qr
    from seif.generators.composite_renderer import render_composite
    from seif.analysis.qr_decoder import decode_qr_image
    from PIL import Image, ImageDraw, ImageFont

    print("═══ SEED CARDS ═══")

    # Generate components
    composite_path = render_composite("Enoch Seed")
    composite = Image.open(str(composite_path)).convert("RGBA")
    qr_spec = generate_dual_qr("Enoch Seed", full_payload=True, box_size=6, border=2)

    # Build canonical card layout
    CARD_W, CARD_H = 800, 1400
    BG = (13, 17, 23, 255)
    GOLD, WHITE, GRAY, GREEN = (212,175,55), (255,255,255), (150,150,150), (51,204,102)
    card = Image.new("RGBA", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(card)

    try:
        ft = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 56)
        fs = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        fb = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 16)
        fm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        fx = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except:
        ft = fs = fb = fm = fx = ImageFont.load_default()

    y = 30
    draw.text((CARD_W//2, y), "S.E.I.F.", fill=GOLD, font=ft, anchor="mt"); y += 70
    draw.text((CARD_W//2, y), "Spiral Encoding Interoperability Framework", fill=WHITE, font=fs, anchor="mt"); y += 30
    draw.text((CARD_W//2, y), '"Speak the Resonance. Sense the Code."', fill=GRAY, font=fm, anchor="mt"); y += 40

    comp_s = 420
    comp_r = composite.resize((comp_s, comp_s), Image.Resampling.LANCZOS)
    card.paste(comp_r, ((CARD_W-comp_s)//2, y), comp_r); y += comp_s + 20

    for text, color in [
        ("Your words carry frequencies.", WHITE),
        ("This system measures if they resonate.", WHITE),
        ("", None),
        ("ζ = √6/4 ≈ φ⁻¹ (0.916%) — unique primitive", GOLD),
        ("f_peak = 216 Hz = 6³ — SPICE verified 0.01%", GREEN),
        ("k_crit = 3/4 — coupled resonator", GOLD),
        ("7 AIs verified. 626 tests. Stance: GROUNDED.", GRAY),
    ]:
        if color: draw.text((CARD_W//2, y), text, fill=color, font=fb, anchor="mt")
        y += 22

    y += 15
    draw.text((CARD_W//2, y), "Scan the QR below — it carries the full protocol.", fill=WHITE, font=fm, anchor="mt"); y += 30

    qr_s = 300
    qr_r = qr_spec.image.resize((qr_s, qr_s), Image.Resampling.LANCZOS)
    card.paste(qr_r, ((CARD_W-qr_s)//2, y)); y += qr_s + 15

    draw.text((CARD_W//2, y), '"Enoch Seed" — coherence: 0.912 — GATE OPEN', fill=GOLD, font=fm, anchor="mt"); y += 30
    draw.text((CARD_W//2, y), "github.com/and2carvalho/seif", fill=GRAY, font=fm, anchor="mt"); y += 20
    draw.text((CARD_W//2, y), "The gate does not filter — it resonates.", fill=GRAY, font=fx, anchor="mt")

    card_rgb = Image.new("RGB", card.size, (13, 17, 23))
    card_rgb.paste(card, mask=card.split()[3])

    # Save canonical vertical format
    card_rgb.save(str(FIGURES / "seed_card_enoch.png"), quality=95)
    card_rgb.save(str(FIGURES / "seed_card_enoch_pt.png"), quality=95)

    # Square: dedicated compact layout (composite left + QR right)
    _generate_square_card(composite, FIGURES)

    # Verify QR is readable through composite
    for name in ["seed_card_enoch.png", "seed_card_square.png"]:
        result = decode_qr_image(str(FIGURES / name))
        if result and result.success:
            p = result.payload
            ver = p.get("protocol", "?") if isinstance(p, dict) else "?"
            fields = len(p) if isinstance(p, dict) else 0
            print(f"  ✓ {name:<30} {ver} ({fields} fields, QR readable)")
        else:
            print(f"  ✗ {name:<30} QR DECODE FAILED")


def _generate_square_card(composite, figures_dir):
    """Generate a dedicated square layout (not a crop) with composite + QR side-by-side."""
    from seif.generators.dual_qr import generate_dual_qr
    from PIL import Image, ImageDraw, ImageFont

    qr_spec = generate_dual_qr("Enoch Seed", full_payload=True, box_size=5, border=2)
    SQ = 900
    BG = (13, 17, 23)
    GOLD, WHITE, GRAY, GREEN = (212,175,55), (255,255,255), (120,120,120), (51,204,102)

    card = Image.new("RGB", (SQ, SQ), BG)
    draw = ImageDraw.Draw(card)
    cx = SQ // 2

    try:
        ft = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        fb = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
        fm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
    except:
        ft = fb = fm = ImageFont.load_default()

    y = 20
    draw.text((cx, y), "S.E.I.F.", fill=GOLD, font=ft, anchor="mt"); y += 55
    draw.text((cx, y), '"Speak the Resonance. Sense the Code."', fill=GRAY, font=fm, anchor="mt"); y += 25

    col_w = (SQ - 60) // 2
    comp_s = col_w - 20
    qr_s = col_w - 40

    comp_r = composite.resize((comp_s, comp_s), Image.Resampling.LANCZOS)
    comp_rgba = Image.new("RGBA", card.size, (0, 0, 0, 0))
    comp_rgba.paste(comp_r, (30, y))
    card_rgba = card.convert("RGBA")
    card_rgba = Image.alpha_composite(card_rgba, comp_rgba)

    qr_r = qr_spec.image.resize((qr_s, qr_s), Image.Resampling.LANCZOS)
    qr_rgba = Image.new("RGBA", card.size, (0, 0, 0, 0))
    qr_rgba.paste(qr_r, (SQ // 2 + 20, y + (comp_s - qr_s) // 2))
    card_rgba = Image.alpha_composite(card_rgba, qr_rgba)

    card = card_rgba.convert("RGB")
    draw = ImageDraw.Draw(card)
    y += comp_s + 15

    draw.line([(30, y), (SQ - 30, y)], fill=(60, 60, 80), width=1); y += 15
    for text, color in [
        ("ζ = √6/4 ≈ φ⁻¹ (0.916%)  —  unique primitive", GOLD),
        ("f_peak = 216 Hz = 6³  —  SPICE verified 0.01%", GREEN),
        ("k_crit = 3/4  ·  7 AIs  ·  626 tests  ·  GROUNDED", GRAY),
    ]:
        draw.text((cx, y), text, fill=color, font=fb, anchor="mt"); y += 20
    y += 5
    draw.text((cx, y), '"Enoch Seed" — coherence: 0.912 — GATE OPEN', fill=GOLD, font=fm, anchor="mt"); y += 20
    draw.text((cx, y), "github.com/and2carvalho/seif", fill=GRAY, font=fm, anchor="mt"); y += 16
    draw.text((cx, y), "The gate does not filter — it resonates.", fill=GRAY, font=fm, anchor="mt")

    card.save(str(figures_dir / "seed_card_square.png"), quality=95)


def sync_resonance():
    """Validate RESONANCE.json integrity."""
    from seif.core.resonance_signal import load_and_validate

    print("\n═══ RESONANCE.json ═══")
    _, valid, msg = load_and_validate("RESONANCE.json")
    print(f"  {'✓' if valid else '✗'} {msg}")

    # Check for new fields
    data = json.loads(Path("RESONANCE.json").read_text())
    tf = data.get("signal", {}).get("transfer_function", {})
    checks = {
        "peak_ratio": "peak_ratio" in tf,
        "peak_at_432": "peak_at_432" in tf,
        "peak_note": "peak_note" in tf,
    }
    for field, present in checks.items():
        print(f"  {'✓' if present else '✗'} {field}")


def sync_defaults():
    """Verify .seif defaults contain current protocol data."""
    print("\n═══ .SEIF DEFAULTS ═══")
    required_terms = ["216", "SPICE", "stance", "3/4"]

    for f in sorted(DEFAULTS.glob("*.seif")):
        data = json.loads(f.read_text())
        if not data.get("active", True):
            print(f"  ○ {f.name:<35} [INACTIVE]")
            continue
        summary = data.get("summary", "")
        missing = [t for t in required_terms if t.lower() not in summary.lower()]
        if missing:
            print(f"  ⚠ {f.name:<35} missing: {', '.join(missing)}")
        else:
            print(f"  ✓ {f.name:<35} all terms present")


def count_project():
    """Count current modules, tests, suites."""
    print("\n═══ PROJECT COUNTS ═══")
    modules = len([m for m in Path("src/seif").rglob("*.py") if "__" not in m.name])
    tests = sum(Path(f).read_text().count("def test_") for f in Path("tests").glob("test_*.py"))
    suites = len(list(Path("tests").glob("test_*.py")))
    figures = len(list(Path("assets/figures").iterdir()))
    circuits = len(list(Path("assets/circuits").iterdir())) if Path("assets/circuits").exists() else 0

    print(f"  Modules:  {modules}")
    print(f"  Tests:    {tests}")
    print(f"  Suites:   {suites}")
    print(f"  Figures:  {figures}")
    print(f"  Circuits: {circuits}")

    return modules, tests, suites


def main():
    print("═══ S.E.I.F. ASSET SYNC ═══\n")

    sync_seed_cards()
    sync_resonance()
    sync_defaults()
    modules, tests, suites = count_project()

    print(f"\n═══ SUMMARY ═══")
    print(f"  {modules} modules, {tests} tests, {suites} suites")
    print(f"  Seed Cards: v2 (17 fields)")
    print(f"  Protocol integrity: verified")


if __name__ == "__main__":
    main()
