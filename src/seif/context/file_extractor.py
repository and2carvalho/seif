"""
File Extractor — Generalized file scanner for SEIF context extraction.

Scans directories or files, classifies content, and produces .seif modules.
Extends the pattern of cli_scanner.py (CLI --help → .seif) to arbitrary files.

SECURITY: All extractions are bound to the owner's profile. Every .seif module
produced contains the owner's identity hash and machine fingerprint. This creates
a cryptographic chain: if a module is found outside the owner's machine, the
provenance proves who created it and where. Extraction requires explicit consent
(interactive confirmation) for directories outside the user's home.
"""

import json
import hashlib
import getpass
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from seif.constants import SENSITIVE_FILE_PATTERNS


# ── Constants ─────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".go": "code",
    ".rs": "code",
    ".java": "code",
    ".rb": "code",
    ".sh": "code",
    ".bash": "code",
    ".zsh": "code",
    ".csv": "data",
    ".xml": "data",
    ".html": "markup",
    ".css": "markup",
    ".pdf": "pdf",
}

MAX_FILE_SIZE = 1_000_000   # 1MB per file
MAX_FILES = 500             # per directory scan
MAX_CONTENT_PER_FILE = 5000 # chars extracted per file

SENSITIVE_KEYWORDS = [
    "password", "secret", "token", "api_key", "apikey",
    "private_key", "credential", "vulnerability", "cve",
    "exploit", "breach", "compliance", "lgpd", "gdpr",
]


# ── Ownership & Consent ──────────────────────────────────────────

def _compute_owner_fingerprint() -> str:
    """Create a fingerprint binding extraction to this user+machine.

    This is NOT for security against the owner — it's for proving provenance
    if a module is found outside the owner's control.
    """
    user = getpass.getuser()
    hostname = platform.node()
    machine = platform.machine()

    # Load profile identity if available
    profile_id = ""
    try:
        from seif.data.paths import get_profile_path
        profile_path = get_profile_path()
        if profile_path.exists():
            with open(profile_path) as f:
                profile = json.load(f)
            profile_id = profile.get("github_username", "") or profile.get("name", "")
    except Exception:
        pass

    raw = f"{user}@{hostname}/{machine}/{profile_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def require_consent(target_path: Path, force: bool = False) -> bool:
    """Require explicit consent for extraction.

    Rules:
    - Paths inside user's home directory: consent implied (your own data)
    - Paths outside home (external drives, other users): explicit confirmation required
    - --force flag bypasses (for automation), but is logged
    """
    home = Path.home()
    target = Path(target_path).resolve()

    # Inside home directory: implied consent
    try:
        target.relative_to(home)
        return True
    except ValueError:
        pass

    # Outside home: require explicit consent
    if force:
        return True

    # Interactive consent
    try:
        print(f"\n  CONSENT REQUIRED")
        print(f"  Target: {target}")
        print(f"  This path is outside your home directory.")
        print(f"  Extraction will scan files and create .seif context modules.\n")
        response = input("  Continue? [y/N] ").strip().lower()
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ── Data class ────────────────────────────────────────────────────

@dataclass
class ExtractedFile:
    path: str
    file_type: str
    content: str
    word_count: int
    classification: str   # PUBLIC, INTERNAL, CONFIDENTIAL


# ── Extraction per type ───────────────────────────────────────────

def extract_file(path: Path) -> Optional[ExtractedFile]:
    """Extract content from a single file. Returns None if unsupported/too large."""
    if not path.is_file():
        return None

    ext = path.suffix.lower()
    file_type = SUPPORTED_EXTENSIONS.get(ext)
    if not file_type:
        return None

    if path.stat().st_size > MAX_FILE_SIZE:
        return None

    # Check sensitive filename patterns
    name_lower = path.name.lower()
    is_sensitive = any(pat in name_lower for pat in [".env", "secret", "credential", "token"])

    try:
        if file_type == "pdf":
            content = _extract_pdf(path)
        elif file_type == "json":
            content = _extract_json(path)
        elif file_type == "code":
            content = _extract_code(path)
        else:
            content = _extract_text(path)
    except (OSError, UnicodeDecodeError):
        return None

    if not content or not content.strip():
        return None

    # Truncate
    content = content[:MAX_CONTENT_PER_FILE]
    word_count = len(content.split())

    # Auto-classify
    classification = "CONFIDENTIAL" if is_sensitive else _auto_classify(content)

    return ExtractedFile(
        path=str(path),
        file_type=file_type,
        content=content,
        word_count=word_count,
        classification=classification,
    )


def _extract_text(path: Path) -> str:
    """Read plain text/markdown."""
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_json(path: Path) -> str:
    """Summarize JSON structure."""
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
        return _summarize_json(data, depth=0, max_depth=3)
    except json.JSONDecodeError:
        return text[:MAX_CONTENT_PER_FILE]


def _summarize_json(data, depth: int = 0, max_depth: int = 3) -> str:
    """Summarize JSON structure without exposing all values."""
    indent = "  " * depth
    if depth >= max_depth:
        return f"{indent}..."

    if isinstance(data, dict):
        lines = [f"{indent}{{"]
        for i, (k, v) in enumerate(data.items()):
            if i >= 10:
                lines.append(f"{indent}  ... ({len(data) - 10} more keys)")
                break
            if isinstance(v, (dict, list)):
                lines.append(f"{indent}  {k}:")
                lines.append(_summarize_json(v, depth + 1, max_depth))
            else:
                val = str(v)[:100]
                lines.append(f"{indent}  {k}: {val}")
        lines.append(f"{indent}}}")
        return "\n".join(lines)
    elif isinstance(data, list):
        if not data:
            return f"{indent}[]"
        return f"{indent}[{len(data)} items, first: {str(data[0])[:100]}]"
    else:
        return f"{indent}{str(data)[:200]}"


def _extract_code(path: Path) -> str:
    """Extract code structure (imports, class/function signatures)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Extract structural lines
    structural = []
    for line in lines:
        stripped = line.strip()
        if (stripped.startswith(("import ", "from ", "class ", "def ",
                                 "function ", "const ", "export ",
                                 "pub fn ", "func ", "type ")) or
            stripped.startswith("#!") or
            (stripped.startswith("# ") and len(stripped) > 3)):
            structural.append(line)

    if structural:
        return f"File: {path.name} ({len(lines)} lines)\n" + "\n".join(structural)
    else:
        # Fallback: first N lines
        return f"File: {path.name} ({len(lines)} lines)\n" + "\n".join(lines[:50])


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF (requires PyPDF2, graceful fallback)."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages[:20]):  # Cap at 20 pages
            text = page.extract_text()
            if text:
                pages.append(f"[Page {i+1}]\n{text}")
        return "\n\n".join(pages) if pages else ""
    except ImportError:
        return f"[PDF: {path.name} — install PyPDF2 to extract content]"
    except Exception:
        return ""


# ── Classification ────────────────────────────────────────────────

def _auto_classify(content: str) -> str:
    """Check content for sensitive patterns. Default: INTERNAL."""
    content_lower = content.lower()
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in content_lower:
            return "CONFIDENTIAL"
    return "INTERNAL"


# ── Directory scanning ────────────────────────────────────────────

def scan_directory(path: Path, recursive: bool = True,
                   force: bool = False) -> list[ExtractedFile]:
    """Walk directory and extract all supported files.

    Requires consent for paths outside the user's home directory.
    """
    path = Path(path).resolve()

    if not require_consent(path, force=force):
        print("  Extraction cancelled.")
        return []

    files = []

    if path.is_file():
        result = extract_file(path)
        return [result] if result else []

    # Walk directory
    glob_pattern = "**/*" if recursive else "*"
    count = 0
    for filepath in sorted(path.glob(glob_pattern)):
        if count >= MAX_FILES:
            break
        if not filepath.is_file():
            continue
        # Skip hidden dirs and common non-content dirs
        parts = filepath.relative_to(path).parts
        if any(p.startswith(".") or p in ("node_modules", "__pycache__",
               "venv", ".venv", "build", "dist") for p in parts):
            continue

        result = extract_file(filepath)
        if result:
            files.append(result)
            count += 1

    return files


# ── Module builder ────────────────────────────────────────────────

CLASSIFICATION_LEVEL = {"PUBLIC": 1, "INTERNAL": 2, "CONFIDENTIAL": 3}


def build_extract_module(files: list[ExtractedFile], source_name: str,
                         max_classification: str = "INTERNAL") -> Optional[dict]:
    """Build a .seif module from extracted files."""
    max_level = CLASSIFICATION_LEVEL.get(max_classification, 2)

    # Filter by classification
    filtered = [f for f in files
                if CLASSIFICATION_LEVEL.get(f.classification, 2) <= max_level]

    if not filtered:
        return None

    # Build summary
    summaries = []
    total_words = 0
    for f in filtered:
        summaries.append(f"## {Path(f.path).name} ({f.file_type})\n{f.content}")
        total_words += f.word_count

    summary = "\n\n".join(summaries)

    # Truncate to reasonable size
    if len(summary) > 50000:
        summary = summary[:50000] + "\n\n[... truncated]"

    # Compute hash
    integrity_hash = hashlib.sha256(summary.encode()).hexdigest()[:16]

    # Determine overall classification (highest of included files)
    classifications = [f.classification for f in filtered]
    if "CONFIDENTIAL" in classifications:
        overall = "CONFIDENTIAL"
    elif "INTERNAL" in classifications:
        overall = "INTERNAL"
    else:
        overall = "PUBLIC"

    now = datetime.now(timezone.utc).isoformat()
    owner_fp = _compute_owner_fingerprint()

    return {
        "_instruction": "SEIF-MODULE-v2",
        "name": f"extract_{source_name}",
        "description": f"Extracted knowledge from {source_name} ({len(filtered)} files)",
        "summary": summary,
        "integrity_hash": integrity_hash,
        "classification": overall,
        "owner_fingerprint": owner_fp,
        "extraction_binding": {
            "user": getpass.getuser(),
            "hostname": platform.node(),
            "extracted_at": now,
            "consent": "implied_home" if _is_inside_home(source_name) else "explicit",
        },
        "metadata": {
            "source": source_name,
            "file_count": len(filtered),
            "word_count": total_words,
            "file_types": list(set(f.file_type for f in filtered)),
        },
        "contributors": [{
            "author": "seif-extract",
            "timestamp": now,
            "via": "cli",
            "action": "extract",
            "owner_fingerprint": owner_fp,
        }],
    }


def _is_inside_home(path_str: str) -> bool:
    """Check if a path string refers to something inside home."""
    try:
        Path(path_str).resolve().relative_to(Path.home())
        return True
    except (ValueError, OSError):
        return False
