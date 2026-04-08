#!/usr/bin/env python3
"""
SEIF Orchestra Probe — lightweight model + circuit discovery for session-start.

Outputs a concise [MODEL ORCHESTRA] block (under 500 tokens) suitable for
injection into Claude Code session context.

Design constraints:
  - Total execution < 5 seconds (SSH/network calls have tight timeouts)
  - Prefers cached registry if fresh discovery is too slow
  - Never imports seif-engine directly (avoids import chain overhead)
  - Loads .env for API key detection without exposing values
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

CIRCUIT_URL = "http://127.0.0.1:7333"
OLLAMA_URL = "http://localhost:11434"
REGISTRY_PATH = Path.home() / ".seif" / "model_registry.json"
HEALTH_PATH = None  # resolved dynamically
ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "seif-internal" / ".env"

# Fallback env path
if not ENV_PATH.exists():
    ENV_PATH = Path.home() / "Documents" / "seif-admin" / "seif-internal" / ".env"


def _load_env():
    """Load .env file into environment (keys only, for detection)."""
    if ENV_PATH.exists():
        try:
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val:
                        os.environ.setdefault(key, val)
        except Exception:
            pass


def _http_get(url: str, timeout: float = 3) -> dict | None:
    """Quick HTTP GET, returns parsed JSON or None."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _probe_circuit() -> dict:
    """Query seif-circuitd status."""
    data = _http_get(f"{CIRCUIT_URL}/status", timeout=2)
    if data and "error" not in data:
        return {
            "connected": data.get("connected", False),
            "machine": data.get("machine", "?"),
            "hub_url": data.get("hub_url", "?"),
            "transport": data.get("transport", "?"),
            "messages": data.get("recent_message_count", 0),
        }
    return {"connected": False, "error": "circuitd not running"}


def _probe_ollama_local() -> list[dict]:
    """Query local Ollama for models."""
    data = _http_get(f"{OLLAMA_URL}/api/tags", timeout=3)
    if not data:
        return []
    models = []
    for m in data.get("models", []):
        name = m.get("name", "unknown")
        size_gb = round(m.get("size", 0) / 1e9, 1)
        models.append({
            "id": f"ollama/{name}",
            "name": name,
            "machine": "local",
            "caps": ["classification", "reasoning"],
            "cost": "free",
            "status": "online",
            "size_gb": size_gb,
        })
    return models


def _probe_api_backends() -> list[dict]:
    """Check which API keys are present (not their validity)."""
    models = []
    if os.environ.get("XAI_API_KEY"):
        models.append({
            "id": "xai/grok-3",
            "name": "Grok 3",
            "machine": "cloud",
            "caps": ["reasoning", "vigilant", "debate"],
            "cost": "token",
            "status": "key_present",
        })
    if os.environ.get("ANTHROPIC_API_KEY"):
        models.append({
            "id": "anthropic/claude-sonnet",
            "name": "Claude Sonnet 4.6",
            "machine": "cloud",
            "caps": ["reasoning", "code", "debate"],
            "cost": "token",
            "status": "key_present",
        })
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        models.append({
            "id": "google/gemini",
            "name": "Gemini",
            "machine": "cloud",
            "caps": ["reasoning", "code"],
            "cost": "token",
            "status": "key_present",
        })
    return models


def _probe_cli_tools() -> list[dict]:
    """Check which CLI AI tools are installed."""
    models = []
    if shutil.which("claude"):
        models.append({
            "id": "cli/claude-code",
            "name": "Claude Code (this session)",
            "machine": "air-m1",
            "caps": ["fs", "code", "writer"],
            "cost": "token",
            "status": "active",
        })
    if shutil.which("gemini"):
        models.append({
            "id": "cli/gemini",
            "name": "Gemini CLI",
            "machine": "air-m1",
            "caps": ["fs", "code", "reasoning"],
            "cost": "free",
            "status": "installed",
        })
    if Path("/Applications/Cursor.app").exists():
        models.append({
            "id": "ide/cursor",
            "name": "Cursor IDE",
            "machine": "air-m1",
            "caps": ["fs", "code", "multi-model"],
            "cost": "subscription",
            "status": "installed",
        })
    return models


def _load_health() -> dict:
    """Load backend health from .seif/backend_health.json."""
    for candidate in [
        Path.cwd() / ".seif" / "backend_health.json",
        Path.home() / ".seif" / "backend_health.json",
    ]:
        if candidate.exists():
            try:
                return json.loads(candidate.read_text())
            except Exception:
                pass
    return {}


def _format_output(models: list[dict], circuit: dict, health: dict) -> str:
    """Format concise orchestra block for session context."""
    lines = ["[MODEL ORCHESTRA]"]

    # Circuit status
    if circuit.get("connected"):
        lines.append(f"Circuit: CONNECTED ({circuit['machine']} via {circuit['transport']})")
    elif circuit.get("error"):
        lines.append("Circuit: OFFLINE (circuitd not running)")
    else:
        lines.append("Circuit: DISCONNECTED")

    # Group models by machine
    by_machine: dict[str, list[dict]] = {}
    for m in models:
        by_machine.setdefault(m["machine"], []).append(m)

    machine_labels = {
        "air-m1": "Air M1",
        "mini-m4": "Mini M4",
        "cloud": "Cloud",
        "local": "Local",
    }

    for machine, mlist in sorted(by_machine.items()):
        label = machine_labels.get(machine, machine)
        online = sum(1 for m in mlist if m["status"] in ("online", "active", "key_present", "installed"))
        lines.append(f"  {label} ({online}/{len(mlist)} available)")
        for m in mlist:
            status_icon = {
                "online": "+", "active": "*", "key_present": "+",
                "installed": "+", "offline": "-", "cached": "~", "unknown": "?",
            }.get(m["status"], "?")
            caps_str = ",".join(m["caps"][:3])
            size_str = f" {m['size_gb']}GB" if m.get("size_gb") else ""
            lines.append(f"    [{status_icon}] {m['name']:<28s} [{caps_str}]{size_str}")

    # Health warnings (only non-healthy)
    unhealthy = {k: v for k, v in health.items() if v.get("status") in ("UNHEALTHY", "DEGRADED")}
    if unhealthy:
        lines.append("  Health warnings:")
        for backend, info in unhealthy.items():
            lines.append(f"    [!] {backend}: {info['status']} — {info.get('last_error', '?')[:60]}")

    # Delegation hint
    delegatable = [m for m in models if m["status"] in ("online", "key_present") and m["id"] != "cli/claude-code"]
    if delegatable:
        names = ", ".join(m["name"] for m in delegatable[:4])
        lines.append(f"Seed-delegatable: {names}")
    else:
        lines.append("Seed-delegatable: none (single-pole mode)")

    return "\n".join(lines)


def main():
    start = time.time()

    # Load .env for API key detection
    _load_env()

    # Collect all probes (local first, fast)
    models = []
    models.extend(_probe_cli_tools())
    models.extend(_probe_ollama_local())
    models.extend(_probe_api_backends())

    # Circuit status
    circuit = _probe_circuit()

    # Health data
    health = _load_health()

    # If we have time budget left and registry has remote models, add cached remote
    elapsed = time.time() - start
    if elapsed < 3.0 and REGISTRY_PATH.exists():
        try:
            registry = json.loads(REGISTRY_PATH.read_text())
            known_ids = {m["id"] for m in models}
            for rm in registry.get("models", []):
                if rm["id"] not in known_ids and rm.get("machine") in ("mini-m4",):
                    models.append({
                        "id": rm["id"],
                        "name": rm["name"],
                        "machine": rm["machine"],
                        "caps": rm.get("capabilities", [])[:3],
                        "cost": rm.get("cost", "?"),
                        "status": "cached",
                        "size_gb": rm.get("size_gb", 0),
                    })
        except Exception:
            pass

    # Output
    print(_format_output(models, circuit, health))

    # Also update the registry cache with fresh timestamp
    try:
        cache = {
            "protocol": "SEIF-MODEL-REGISTRY-v1",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "probe_ms": int((time.time() - start) * 1000),
            "models": models,
            "circuit": circuit,
        }
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    except Exception:
        pass


if __name__ == "__main__":
    main()
