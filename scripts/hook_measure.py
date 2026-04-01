#!/usr/bin/env python3
"""
SEIF Hook — Measures resonance of the user's message via Triple Gate.

Called by Claude Code hook on user_prompt_submit.
Reads the user's message from stdin (JSON), measures it, and outputs
a brief resonance annotation to stderr (which Claude Code shows as context).

This is MEASUREMENT, not filtering. The hook never blocks or modifies
the message — it only annotates.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.core.triple_gate import evaluate


def main():
    try:
        # Claude Code hooks receive JSON on stdin
        data = json.load(sys.stdin)
        message = data.get("message", "") or data.get("content", "") or str(data)
    except (json.JSONDecodeError, AttributeError):
        # Fallback: read raw text
        message = sys.stdin.read().strip()

    if not message or len(message) < 2:
        return

    result = evaluate(message[:500])  # cap at 500 chars for speed

    # Output annotation to stderr (Claude Code shows this as hook feedback)
    annotation = (
        f"[SEIF METADATA] "
        f"Triple Gate: {result.status} ({result.layers_open}/3) | "
        f"Score: {result.composite_score:.3f} | "
        f"ASCII root: {result.ascii_gate.digital_root} ({result.ascii_gate.phase.name}) | "
        f"Coherence: {result.resonance_score:.3f}"
    )
    print(annotation, file=sys.stderr)


if __name__ == "__main__":
    main()
