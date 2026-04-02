"""
Doc Generator — Generate documentation from .seif context modules.

The reverse of --scan and --compress: reads compressed .seif knowledge
and expands it into structured, readable documentation.

Implemented during SEIF solidification phase (2026-03-31).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Category display order and titles
CATEGORY_TITLES = {
    "decisions": "Architectural Decisions",
    "patterns": "Code Patterns & Conventions",
    "feedback": "Interaction Guidelines",
    "intent": "Project Intent & Goals",
    "context": "External Context & Constraints",
}


def load_modules_by_category(context_repo: str) -> dict[str, list[dict]]:
    """Load all .seif modules grouped by category from mapper.json."""
    mapper_path = Path(context_repo) / "mapper.json"
    if not mapper_path.exists():
        return {}

    with open(mapper_path, encoding="utf-8") as f:
        mapper = json.load(f)

    modules_by_cat = {}
    for entry in mapper.get("modules", []):
        cat = entry.get("category", "context")
        path = Path(context_repo) / entry["path"]

        if not path.exists():
            continue

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if not data.get("active", True):
            continue

        if cat not in modules_by_cat:
            modules_by_cat[cat] = []

        modules_by_cat[cat].append({
            "source": data.get("source", entry["path"]),
            "summary": data.get("summary", ""),
            "classification": data.get("classification", "INTERNAL"),
            "version": data.get("version", 1),
            "updated_at": data.get("updated_at", entry.get("last_updated", "")),
            "contributors": data.get("contributors", []),
            "integrity_hash": data.get("integrity_hash", ""),
            "compression_ratio": data.get("compression_ratio", 0),
            "path": str(path),
        })

    return modules_by_cat


def generate_docs(context_repo: str, output_dir: str,
                  max_classification: str = "INTERNAL",
                  project: str = None) -> list[str]:
    """Generate documentation files from .seif modules.

    Reads all active modules, groups by category, and produces
    one markdown file per category plus an index.

    Args:
        context_repo: Path to .seif/ directory
        output_dir: Where to write the generated docs
        max_classification: Maximum classification level to include
        project: Filter to specific project (None = all)

    Returns:
        List of generated file paths.
    """
    LEVELS = {"PUBLIC": 1, "INTERNAL": 2, "CONFIDENTIAL": 3}
    max_level = LEVELS.get(max_classification, 2)

    modules_by_cat = load_modules_by_category(context_repo)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    generated = []
    index_entries = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for cat, modules in sorted(modules_by_cat.items()):
        # Filter by classification
        filtered = [
            m for m in modules
            if LEVELS.get(m["classification"], 2) <= max_level
        ]
        if not filtered:
            continue

        # Filter by project if specified
        if project:
            filtered = [
                m for m in filtered
                if project in m["source"]
            ]
            if not filtered:
                continue

        title = CATEGORY_TITLES.get(cat, cat.title())
        filename = f"{cat}.md"
        filepath = out / filename

        lines = [
            f"# {title}",
            f"",
            f"> Auto-generated from .seif context modules ({now})",
            f"> Classification: up to {max_classification}",
            f"> Modules: {len(filtered)}",
            f"",
        ]

        for m in filtered:
            lines.append(f"---")
            lines.append(f"")

            # Module header
            source = m["source"]
            lines.append(f"## {source}")
            lines.append(f"")

            meta = []
            try:
                ver = int(m.get("version") or 1)
                if ver > 1:
                    meta.append(f"v{ver}")
            except (ValueError, TypeError):
                pass
            cls = m.get("classification")
            if cls and cls != "INTERNAL":
                meta.append(str(cls))
            try:
                ratio = float(m.get("compression_ratio") or 0)
                if ratio > 0:
                    meta.append(f"{ratio:.0f}:1 compression")
            except (ValueError, TypeError):
                pass
            updated = m.get("updated_at")
            if updated:
                meta.append(f"updated {str(updated)[:10]}")
            if meta:
                lines.append(f"*{' | '.join(meta)}*")
                lines.append(f"")

            # Summary content
            lines.append(m["summary"])
            lines.append(f"")

            # Contributors
            if m["contributors"]:
                lines.append(f"**Contributors:** " + ", ".join(
                    c.get("author", "unknown")
                    for c in m["contributors"]
                ))
                lines.append(f"")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        generated.append(str(filepath))

        # Index entry
        total_words = sum(len(m["summary"].split()) for m in filtered)
        index_entries.append(
            f"- [{title}]({filename}) — {len(filtered)} modules, "
            f"~{total_words} words"
        )

    # Generate index
    if index_entries:
        index_path = out / "INDEX.md"
        index_lines = [
            f"# SEIF Generated Documentation",
            f"",
            f"> Generated from .seif context ({now})",
            f"> Source: `{context_repo}`",
            f"",
        ]

        # Add pending observations if available
        mapper_path = Path(context_repo) / "mapper.json"
        if mapper_path.exists():
            with open(mapper_path, encoding="utf-8") as f:
                mapper = json.load(f)
            pending = mapper.get("pending_observations", [])
            if pending:
                index_lines.append(f"## Pending Items ({len(pending)})")
                index_lines.append(f"")
                for p in pending[:10]:
                    index_lines.append(f"- {p[:120]}")
                index_lines.append(f"")

        index_lines.append(f"## Documentation")
        index_lines.append(f"")
        index_lines.extend(index_entries)

        index_path.write_text("\n".join(index_lines), encoding="utf-8")
        generated.insert(0, str(index_path))

    return generated


def generate_changelog(context_repo: str, output: str = None) -> str:
    """Generate CHANGELOG.md from decisions.seif contributions.

    Each contribution in decisions.seif becomes a changelog entry,
    ordered by date (newest first).
    """
    modules_by_cat = load_modules_by_category(context_repo)
    decisions = modules_by_cat.get("decisions", [])

    if not decisions:
        return "No decisions modules found."

    entries = []
    for m in decisions:
        summary = m["summary"]
        # Each "### Contribution by" or "### " section is an entry
        sections = summary.split("\n### ")
        for section in sections[1:]:  # skip the header
            lines = section.strip().split("\n")
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

            # Extract date from title if present
            date = ""
            for part in title.split("("):
                if "202" in part:
                    date = part.split(")")[0].strip().split(",")[0].strip()
                    break

            entries.append({
                "title": title,
                "body": body[:500],
                "date": date,
                "source": m["source"],
            })

    # Sort by date (newest first)
    entries.sort(key=lambda e: e["date"], reverse=True)

    lines = [
        "# Changelog",
        "",
        "> Auto-generated from decisions.seif modules",
        "",
    ]

    current_date = ""
    for e in entries:
        if e["date"] and e["date"] != current_date:
            current_date = e["date"]
            lines.append(f"## {current_date}")
            lines.append("")

        lines.append(f"### {e['title']}")
        if e["body"]:
            lines.append("")
            lines.append(e["body"])
        lines.append("")

    text = "\n".join(lines)

    if output:
        Path(output).write_text(text, encoding="utf-8")

    return text
