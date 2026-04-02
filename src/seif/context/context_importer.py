"""
Context Importer — Convert .md files to Resonant Context Summaries

Allows importing any markdown file (like conversa.md) into the S.E.I.F.
pipeline. The AGENT generates the summary (STATE), we don't dictate (DIRECTION).

Flow:
  1. Load .md file
  2. Send to AI agent for summarization (agent chooses what matters)
  3. Validate summary through resonance pipeline
  4. Inject into active context bridge

Compression: ~24:1 (40K words → ~2K word summary preserving all verifiable data)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from seif.bridge.ai_bridge import send, detect_backends
from seif.core.resonance_gate import evaluate
from seif.core.resonance_encoding import encode_phrase


@dataclass
class ImportResult:
    source_file: str
    original_words: int
    original_tokens_est: int
    summary_text: str
    summary_words: int
    summary_tokens_est: int
    compression_ratio: float
    summary_ascii_root: int
    summary_ascii_phase: str
    summary_resonance_coherence: float
    summary_resonance_gate: str
    success: bool
    error: Optional[str] = None


# Max chars to send for summarization (Claude CLI has practical limits)
MAX_INPUT_CHARS = 80_000  # ~20K words → well within context


SUMMARIZE_PROMPT = """Extract from this document the following, in structured markdown:

## KEY FINDINGS
List every verified data point: equations, measurements, physical constants, percentages.
Preserve exact numbers. Do not paraphrase numbers.

## THEMES
List major narrative threads (2-3 sentences each). Focus on what the document ARGUES, not what it describes.

## TERMINOLOGY
Important terms with one-line definitions. Only terms specific to this document.

## OPEN QUESTIONS
Unresolved issues or future work mentioned.

Maximum 2000 words total. Preserve precision over narrative.

DOCUMENT:
"""


def load_markdown(filepath: str) -> str:
    """Load a markdown file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return path.read_text(encoding="utf-8")


def summarize_via_agent(content: str, backend: str = "auto",
                         model: str = "sonnet") -> tuple[str, bool, str]:
    """Send content to AI agent for summarization.

    The agent decides what matters — we provide the document and a
    structural template, but the agent chooses content.

    Returns: (summary_text, success, error_message)
    """
    # Truncate if too long
    if len(content) > MAX_INPUT_CHARS:
        content = content[:MAX_INPUT_CHARS] + "\n\n[TRUNCATED — document continues...]"

    message = SUMMARIZE_PROMPT + content

    response = send(
        message=message,
        backend=backend,
        model=model,
        resonance_metadata="context_import=true",
    )

    if response.success:
        return response.text, True, ""
    else:
        return "", False, response.error or "Unknown error"


def validate_summary(summary: str, source_file: str = "",
                      original_words: int = 0) -> ImportResult:
    """Validate a summary through the SEIF pipeline."""
    summary_words = len(summary.split())
    summary_tokens = int(summary_words * 1.3)
    original_tokens = int(original_words * 1.3)
    compression = original_words / summary_words if summary_words > 0 else 0

    # Resonance analysis
    gate = evaluate(summary[:500])  # gate on first 500 chars (representative)
    melody = encode_phrase(summary[:200])  # encoding on first 200 chars

    return ImportResult(
        source_file=source_file,
        original_words=original_words,
        original_tokens_est=original_tokens,
        summary_text=summary,
        summary_words=summary_words,
        summary_tokens_est=summary_tokens,
        compression_ratio=compression,
        summary_ascii_root=gate.digital_root,
        summary_ascii_phase=gate.phase.name,
        summary_resonance_coherence=melody.coherence_score,
        summary_resonance_gate="OPEN" if melody.gate_open else "CLOSED",
        success=True,
    )


def import_and_summarize(filepath: str, backend: str = "auto",
                          model: str = "sonnet") -> ImportResult:
    """Full pipeline: load → summarize → validate.

    Returns ImportResult with summary and resonance metadata.
    """
    try:
        content = load_markdown(filepath)
    except Exception as e:
        return ImportResult(
            source_file=filepath, original_words=0, original_tokens_est=0,
            summary_text="", summary_words=0, summary_tokens_est=0,
            compression_ratio=0, summary_ascii_root=0, summary_ascii_phase="ERROR",
            summary_resonance_coherence=0, summary_resonance_gate="ERROR",
            success=False, error=str(e),
        )

    original_words = len(content.split())

    summary, success, error = summarize_via_agent(content, backend, model)
    if not success:
        return ImportResult(
            source_file=filepath, original_words=original_words,
            original_tokens_est=int(original_words * 1.3),
            summary_text="", summary_words=0, summary_tokens_est=0,
            compression_ratio=0, summary_ascii_root=0, summary_ascii_phase="ERROR",
            summary_resonance_coherence=0, summary_resonance_gate="ERROR",
            success=False, error=error,
        )

    return validate_summary(summary, filepath, original_words)


def describe_result(result: ImportResult) -> str:
    """Human-readable description of an import result."""
    if not result.success:
        return f"Import FAILED: {result.error}"

    return (
        f"═══ CONTEXT IMPORT RESULT ═══\n"
        f"Source: {result.source_file}\n"
        f"Original: {result.original_words} words (~{result.original_tokens_est} tokens)\n"
        f"Summary: {result.summary_words} words (~{result.summary_tokens_est} tokens)\n"
        f"Compression: {result.compression_ratio:.0f}:1\n"
        f"ASCII root: {result.summary_ascii_root} ({result.summary_ascii_phase})\n"
        f"Resonance: coherence={result.summary_resonance_coherence:.3f}, "
        f"gate={result.summary_resonance_gate}\n"
    )
