"""
Context Ingest — Filter external text by project relevance and contribute.

Turns noisy sources (meeting transcripts, dailies, Slack digests, emails)
into focused project context by using the existing .seif as a relevance filter.

Flow:
  1. Load raw text (file, stdin, or string)
  2. Load project .seif for context (what is this project about?)
  3. AI filters: extract only what is relevant to THIS project
  4. Quality gate scores the extraction
  5. Contribute filtered content to project.seif

Usage:
  seif --ingest meeting_notes.txt --project .seif/project.seif --author "daily"
  cat transcript.txt | seif --ingest - --project .seif/project.seif
  seif --ingest "Raw text here" --project .seif/project.seif
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from seif.bridge.ai_bridge import send, detect_backends
from seif.context.context_manager import load_module, contribute_to_module
from seif.analysis.quality_gate import assess


FILTER_PROMPT_TEMPLATE = """You are a context filter for a software project. Your job is to extract ONLY the information relevant to the project described below.

## PROJECT CONTEXT
{project_context}

## RAW INPUT (meeting transcript / daily / notes)
{raw_text}

## INSTRUCTIONS
Extract from the raw input ONLY items relevant to this specific project. Ignore everything else.

Output in this exact format:

### Decisions
- (list decisions made about this project, if any)

### Action Items
- (list action items for this project, with owner if mentioned)

### Blockers
- (list blockers or risks for this project, if any)

### Context Updates
- (new information, status changes, or findings relevant to this project)

Rules:
- If NOTHING in the raw input is relevant to this project, respond with exactly: "NO_RELEVANT_CONTENT"
- Be concise. Each item should be 1-2 sentences max.
- Preserve names, dates, numbers, and specific technical details.
- Do NOT add information that wasn't in the raw input.
- Maximum 500 words total.
"""


@dataclass
class IngestResult:
    """Result of ingesting external text into a project .seif."""
    source: str              # "file:path", "stdin", or "string"
    raw_words: int
    filtered_text: str
    filtered_words: int
    compression_ratio: float
    quality_score: float
    quality_grade: str
    relevant: bool           # False if NO_RELEVANT_CONTENT
    contributed: bool        # True if successfully contributed to .seif
    module_version: int = 0
    module_hash: str = ""
    error: str = ""


def _load_raw_text(source: str) -> tuple[str, str]:
    """Load raw text from file, stdin, or string.

    Returns: (text, source_label)
    """
    if source == "-":
        text = sys.stdin.read()
        return text, "stdin"

    path = Path(source)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore"), f"file:{path.name}"

    # Treat as raw string
    return source, "string"


def _load_project_context(project_seif_path: str) -> str:
    """Load project summary from .seif file."""
    module = load_module(project_seif_path)
    return module.summary


def _filter_via_ai(raw_text: str, project_context: str,
                   backend: str = "auto",
                   model: str = "sonnet") -> tuple[str, bool, str]:
    """Use AI to filter raw text by project relevance.

    Returns: (filtered_text, success, error)
    """
    # Truncate raw text if too long (keep first 60K chars)
    if len(raw_text) > 60_000:
        raw_text = raw_text[:60_000] + "\n\n[TRUNCATED]"

    # Truncate project context (keep first 2000 chars)
    project_context = project_context[:2000]

    prompt = FILTER_PROMPT_TEMPLATE.format(
        project_context=project_context,
        raw_text=raw_text,
    )

    response = send(
        message=prompt,
        backend=backend,
        model=model,
        resonance_metadata="ingest_filter=true",
    )

    if response.success:
        return response.text.strip(), True, ""
    return "", False, response.error or "AI backend unavailable"


def ingest(source: str, project_seif_path: str,
           author: str = "ingest", via: str = "meeting",
           backend: str = "auto", model: str = "sonnet") -> IngestResult:
    """Ingest external text, filter by project relevance, contribute to .seif.

    Args:
        source: Raw text, file path, or "-" for stdin.
        project_seif_path: Path to the project .seif file.
        author: Author name for contribution.
        via: Source label (e.g. "daily", "meeting", "slack").
        backend: AI backend for filtering.
        model: AI model for filtering.

    Returns:
        IngestResult with filtering and contribution details.
    """
    # Load raw text
    raw_text, source_label = _load_raw_text(source)
    raw_words = len(raw_text.split())

    if raw_words < 5:
        return IngestResult(
            source=source_label, raw_words=raw_words,
            filtered_text="", filtered_words=0,
            compression_ratio=0, quality_score=0,
            quality_grade="F", relevant=False, contributed=False,
            error="Input too short (< 5 words)",
        )

    # Load project context
    try:
        project_context = _load_project_context(project_seif_path)
    except Exception as e:
        return IngestResult(
            source=source_label, raw_words=raw_words,
            filtered_text="", filtered_words=0,
            compression_ratio=0, quality_score=0,
            quality_grade="F", relevant=False, contributed=False,
            error=f"Cannot load project .seif: {e}",
        )

    # Filter via AI
    filtered_text, success, error = _filter_via_ai(
        raw_text, project_context, backend, model,
    )

    if not success:
        return IngestResult(
            source=source_label, raw_words=raw_words,
            filtered_text="", filtered_words=0,
            compression_ratio=0, quality_score=0,
            quality_grade="F", relevant=False, contributed=False,
            error=error,
        )

    # Check if anything was relevant
    if "NO_RELEVANT_CONTENT" in filtered_text:
        return IngestResult(
            source=source_label, raw_words=raw_words,
            filtered_text="", filtered_words=0,
            compression_ratio=0, quality_score=0,
            quality_grade="-", relevant=False, contributed=False,
        )

    filtered_words = len(filtered_text.split())
    compression = raw_words / filtered_words if filtered_words > 0 else 0

    # Quality gate on filtered content
    verdict = assess(filtered_text, role="human")

    # Contribute to project.seif
    try:
        module, path = contribute_to_module(
            project_seif_path, filtered_text,
            author=author, via=via,
        )
        return IngestResult(
            source=source_label, raw_words=raw_words,
            filtered_text=filtered_text, filtered_words=filtered_words,
            compression_ratio=round(compression, 1),
            quality_score=verdict.score, quality_grade=verdict.grade,
            relevant=True, contributed=True,
            module_version=module.version, module_hash=module.integrity_hash,
        )
    except Exception as e:
        return IngestResult(
            source=source_label, raw_words=raw_words,
            filtered_text=filtered_text, filtered_words=filtered_words,
            compression_ratio=round(compression, 1),
            quality_score=verdict.score, quality_grade=verdict.grade,
            relevant=True, contributed=False,
            error=f"Contribute failed: {e}",
        )


def describe_ingest(r: IngestResult) -> str:
    """Human-readable ingest report."""
    lines = []

    if r.error and not r.relevant:
        lines.append(f"Ingest FAILED: {r.error}")
        return "\n".join(lines)

    icon = "🟢" if r.contributed else ("⚪" if not r.relevant else "🔴")
    lines.append(f"{icon} Ingest: {r.source}")
    lines.append(f"  Raw:       {r.raw_words} words")

    if not r.relevant:
        lines.append(f"  Result:    No content relevant to this project")
        return "\n".join(lines)

    lines.append(f"  Filtered:  {r.filtered_words} words ({r.compression_ratio}:1 compression)")
    lines.append(f"  Quality:   Grade {r.quality_grade} (score: {r.quality_score:.3f})")

    if r.contributed:
        lines.append(f"  Contributed: version {r.module_version} (hash: {r.module_hash})")
    else:
        lines.append(f"  Contributed: FAILED — {r.error}")

    return "\n".join(lines)
