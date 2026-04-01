#!/usr/bin/env python3
"""Generate the startup prompt for injection into Claude/Gemini CLI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seif.context.context_manager import build_startup_context

prompt = build_startup_context()
print(prompt)
