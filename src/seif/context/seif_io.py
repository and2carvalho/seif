"""
SEIF I/O — Atomic file operations with locking for concurrent session safety.

Problem: Multiple terminal sessions running seif simultaneously modify the same
.seif files and mapper.json, causing lost writes and broken hashes.

Solution: Three layers of protection:
  1. File locking (fcntl.flock) — prevents concurrent writes to same file
  2. Atomic writes (temp + os.replace) — no partial/corrupt files on crash
  3. CAS (Compare-And-Swap) — detects stale reads via integrity hash

Usage:
  from seif.context.seif_io import atomic_write_json, locked_read_modify_write

  # Simple atomic write (no read dependency)
  atomic_write_json(path, data)

  # Read-modify-write with locking (for contribute, mapper updates, etc.)
  def updater(current_data):
      current_data["version"] += 1
      return current_data
  result = locked_read_modify_write(path, updater)
"""

import fcntl
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional


# Lock directory — stores .lock files alongside targets
# Using a dedicated dir prevents lock files from polluting project dirs
_LOCK_TIMEOUT = 10.0   # seconds to wait for lock before giving up
_LOCK_RETRY = 0.05     # seconds between lock attempts


class SeifIOError(Exception):
    """Raised when an I/O operation fails due to concurrency."""
    pass


class StaleReadError(SeifIOError):
    """Raised when a CAS check detects the file changed since it was read."""
    pass


class LockTimeoutError(SeifIOError):
    """Raised when a file lock cannot be acquired within timeout."""
    pass


def _lock_path(target: Path) -> Path:
    """Get the lock file path for a target file."""
    return target.with_suffix(target.suffix + ".lock")


def atomic_write_json(path: Path, data, ensure_ascii: bool = False) -> None:
    """Write JSON atomically: write to temp file, then rename.

    This prevents partial/corrupt files if the process crashes mid-write.
    Safe for concurrent readers (they see either old or new, never partial).

    Args:
        path: Target file path.
        data: JSON-serializable object (dict, list, etc.).
        ensure_ascii: JSON encoding flag.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory (same filesystem = atomic rename)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=ensure_ascii)
            f.flush()
            os.fsync(f.fileno())
        # Atomic rename (POSIX guarantees this on same filesystem)
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def acquire_lock(path: Path, timeout: float = _LOCK_TIMEOUT) -> int:
    """Acquire an exclusive file lock. Returns the lock file descriptor.

    Uses fcntl.flock (advisory lock). The lock is released when the fd is closed.

    Args:
        path: The file to lock (lock is on path.lock alongside it).
        timeout: Max seconds to wait.

    Returns:
        File descriptor of the lock file. Caller must close it to release.

    Raises:
        LockTimeoutError: If lock cannot be acquired within timeout.
    """
    lock_file = _lock_path(Path(path))
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o644)
    deadline = time.monotonic() + timeout

    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Write PID for debugging
            os.write(fd, f"{os.getpid()}\n".encode())
            return fd
        except (OSError, BlockingIOError):
            if time.monotonic() >= deadline:
                os.close(fd)
                raise LockTimeoutError(
                    f"Could not acquire lock on {path} within {timeout}s. "
                    f"Another seif session may be writing to it."
                )
            time.sleep(_LOCK_RETRY)


def release_lock(fd: int) -> None:
    """Release a file lock acquired by acquire_lock."""
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def locked_read_modify_write(
    path: Path,
    updater: Callable,
    default=None,
    timeout: float = _LOCK_TIMEOUT,
):
    """Read a JSON file, apply an update function, and write back — all under lock.

    This is the core primitive for safe concurrent access to .seif and mapper.json.
    The lock prevents other sessions from modifying the file between read and write.

    Args:
        path: JSON file to modify.
        updater: Function that receives current data and returns updated data.
                 Must be a pure function of the input (no side effects that can't be retried).
        default: Default value if file doesn't exist yet (dict, list, or any JSON-serializable).
        timeout: Max seconds to wait for lock.

    Returns:
        The updated data.

    Raises:
        LockTimeoutError: If lock cannot be acquired.
    """
    path = Path(path)
    fd = acquire_lock(path, timeout)
    try:
        # Read current state (under lock)
        if path.exists() and path.stat().st_size > 0:
            with open(path, "r", encoding="utf-8") as f:
                current = json.load(f)
        elif default is not None:
            current = default.copy() if hasattr(default, 'copy') else default
        else:
            raise FileNotFoundError(f"No such file: {path}")

        # Apply update
        updated = updater(current)

        # Write atomically
        atomic_write_json(path, updated)

        return updated
    finally:
        release_lock(fd)


def locked_write_json(path: Path, data: dict, timeout: float = _LOCK_TIMEOUT) -> None:
    """Write JSON with exclusive lock (no read dependency).

    Use this for fresh writes where you don't need to read first.
    For read-modify-write, use locked_read_modify_write() instead.
    """
    path = Path(path)
    fd = acquire_lock(path, timeout)
    try:
        atomic_write_json(path, data)
    finally:
        release_lock(fd)


def cas_write_json(
    path: Path,
    data: dict,
    expected_hash: str,
    hash_field: str = "integrity_hash",
) -> bool:
    """Compare-And-Swap write: only write if the file's hash matches expected.

    This detects stale reads without locking. If another session modified the
    file since you read it, the hash won't match and the write is rejected.

    Args:
        path: Target file.
        data: New data to write.
        expected_hash: The hash you read earlier (from the file's hash_field).
        hash_field: Which field contains the integrity hash.

    Returns:
        True if write succeeded, False if hash mismatch (file was modified).
    """
    path = Path(path)
    fd = acquire_lock(path)
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                current = json.load(f)
            current_hash = current.get(hash_field, "")
            if current_hash != expected_hash:
                return False  # File was modified by another session

        atomic_write_json(path, data)
        return True
    finally:
        release_lock(fd)


def compute_hash(text: str) -> str:
    """Compute SEIF integrity hash (SHA256[:16])."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]
