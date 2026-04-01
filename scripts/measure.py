#!/usr/bin/env python3
"""
Measure a message through the SEIF pipeline.

Usage:
    PYTHONPATH=src python scripts/measure.py "your message"
    PYTHONPATH=src python scripts/measure.py "AI response" --ai

Outputs a coherence badge that you can share with the AI in conversation.
"""
import sys
import argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from seif.core.resonance_gate import evaluate
from seif.core.resonance_encoding import encode_phrase


def measure(text: str, source: str = "human") -> str:
    gate = evaluate(text[:500])
    melody = encode_phrase(text[:200])

    gate_icon = "🟢" if melody.gate_open or gate.gate_open else "🔴"
    badge = (
        f"{gate_icon} [{source.upper()}] "
        f"root={gate.digital_root} ({gate.phase.name}) "
        f"coherence={melody.coherence_score:.4f} "
        f"gate={'OPEN' if melody.gate_open else 'CLOSED'}"
    )

    detail = (
        f"\n  ASCII: root {gate.digital_root}, {gate.phase.name}, "
        f"{'OPEN' if gate.gate_open else 'CLOSED'}"
        f"\n  Resonance: coherence {melody.coherence_score:.4f}, "
        f"{'OPEN' if melody.gate_open else 'CLOSED'}"
        f"\n  Text: \"{text[:60]}{'...' if len(text) > 60 else ''}\""
    )
    return badge + detail


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure a message through SEIF")
    parser.add_argument("text", help="The message to measure")
    parser.add_argument("--ai", action="store_true", help="Mark as AI response (default: human)")
    args = parser.parse_args()

    source = "ai" if args.ai else "human"
    print(measure(args.text, source))
    print("\nCopy the badge line above and share it in your AI conversation.")
