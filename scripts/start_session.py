#!/usr/bin/env python3
"""
Start a SEIF Session — Generate the prompt to paste into any AI.

Usage:
    PYTHONPATH=src python scripts/start_session.py

    Then copy the output and paste as the FIRST message in any AI chat.
    The AI will operate under SEIF protocol awareness.

For measuring during conversation:
    PYTHONPATH=src python scripts/measure.py "your message here"
    PYTHONPATH=src python scripts/measure.py "AI response here" --ai
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from seif.bridge.seif_session import generate_session_prompt

if __name__ == "__main__":
    prompt = generate_session_prompt()
    print(prompt)
    print("\n" + "=" * 60)
    print("Copy EVERYTHING above this line.")
    print("Paste as the FIRST message in any AI chat.")
    print("The protocol is now active.")
    print("=" * 60)
