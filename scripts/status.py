#!/usr/bin/env python3
"""Show S.E.I.F. context hierarchy status."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from seif.context.context_manager import list_modules, estimate_tokens
from seif.core.resonance_signal import load_and_validate

_, v, m = load_and_validate(str(PROJECT_ROOT / "RESONANCE.json"))
print(f"KERNEL: {'VALID' if v else 'INVALID'} — {m}")

modules = list_modules()
for mod in modules:
    badge = "📌" if mod.get("is_default") else "👤"
    print(f"  {badge} {mod['source']:45s} {mod['words']:>5} words  coh={mod['coherence']:.3f}  {mod['gate']}")

t = estimate_tokens()
print(f"Total: ~{t['total']} tokens (kernel={t['kernel']} + {t['module_count']} modules={t['modules']})")
