"""
OpenTimestamps integration — Bitcoin-anchored proof of existence.

Provides immutable, court-admissible timestamps for .seif modules.
Each stamp creates a .ots proof file that can be verified against
the Bitcoin blockchain forever, without any third-party trust.

Usage:
    seif stamp module.seif        → creates module.seif.ots
    seif verify-stamp module.seif → verifies against Bitcoin blockchain
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, Tuple


def _find_ots() -> Optional[str]:
    """Find the ots binary (installed via pip or system)."""
    # Check venv first
    venv_ots = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "ots"
    if venv_ots.exists():
        return str(venv_ots)
    return shutil.which("ots")


def stamp(file_path: Path) -> Tuple[bool, str]:
    """Stamp a file with OpenTimestamps.

    Creates file_path.ots containing the Bitcoin-anchored proof.
    Returns (success, message).
    """
    ots_bin = _find_ots()
    if not ots_bin:
        return False, "OpenTimestamps not installed. Run: pip install opentimestamps-client"

    file_path = Path(file_path).resolve()
    if not file_path.exists():
        return False, f"File not found: {file_path}"

    ots_path = file_path.with_suffix(file_path.suffix + ".ots")

    # Don't re-stamp if proof already exists
    if ots_path.exists():
        return True, f"Already stamped: {ots_path.name}"

    try:
        result = subprocess.run(
            [ots_bin, "stamp", str(file_path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and ots_path.exists():
            return True, f"Stamped: {ots_path.name}"
        else:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return False, f"Stamp failed: {error}"
    except subprocess.TimeoutExpired:
        return False, "Stamp timeout (calendar server unreachable?)"
    except Exception as e:
        return False, str(e)


def verify(file_path: Path) -> Tuple[bool, str]:
    """Verify a file's OpenTimestamps proof.

    Checks file_path.ots against the Bitcoin blockchain.
    Returns (success, message).
    """
    ots_bin = _find_ots()
    if not ots_bin:
        return False, "OpenTimestamps not installed."

    file_path = Path(file_path).resolve()
    ots_path = file_path.with_suffix(file_path.suffix + ".ots")

    if not ots_path.exists():
        return False, f"No proof found: {ots_path.name}. Run: seif stamp {file_path.name}"

    try:
        result = subprocess.run(
            [ots_bin, "verify", str(ots_path)],
            capture_output=True, text=True, timeout=60,
        )
        output = result.stdout.strip() + "\n" + result.stderr.strip()
        output = output.strip()

        if "Success" in output or "Bitcoin" in output:
            return True, output
        elif "Pending" in output or "pending" in output:
            return True, f"Pending confirmation (Bitcoin block not yet mined): {output}"
        else:
            return False, output or "Verification failed"
    except subprocess.TimeoutExpired:
        return False, "Verify timeout"
    except Exception as e:
        return False, str(e)


def stamp_directory(directory: Path) -> list[dict]:
    """Stamp all .seif files in a directory."""
    results = []
    for seif_file in sorted(Path(directory).rglob("*.seif")):
        # Skip if already has .ots
        ots_file = seif_file.with_suffix(".seif.ots")
        if ots_file.exists():
            results.append({"file": seif_file.name, "status": "already stamped"})
            continue

        ok, msg = stamp(seif_file)
        results.append({
            "file": seif_file.name,
            "status": "stamped" if ok else "failed",
            "message": msg,
        })
    return results


def info(file_path: Path) -> Optional[str]:
    """Get info about an OTS proof."""
    ots_bin = _find_ots()
    if not ots_bin:
        return None

    ots_path = Path(file_path).resolve().with_suffix(
        Path(file_path).suffix + ".ots"
    )
    if not ots_path.exists():
        return None

    try:
        result = subprocess.run(
            [ots_bin, "info", str(ots_path)],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None
