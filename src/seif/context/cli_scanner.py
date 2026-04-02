"""
CLI Scanner — Parse program --help output into .seif knowledge modules.

Scans any CLI program's help output and generates a structured .seif module
containing commands, flags, subcommands, and usage patterns. Any AI session
that loads this module can use the program expertly.

Strategy: Hybrid (regex heuristics for 80% of common CLI formats,
structured extraction as fallback).

Part of the SEIF solidification phase (2026-03-31).
Approved by: André (direction), Grok (architecture), DeepSeek (security review).
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Flag:
    short: str = ""         # e.g. "-f"
    long: str = ""          # e.g. "--force"
    arg: str = ""           # e.g. "FILE", "N", "" (no arg)
    description: str = ""
    required: bool = False


@dataclass
class Subcommand:
    name: str = ""
    description: str = ""
    flags: list[Flag] = field(default_factory=list)
    subcommands: list["Subcommand"] = field(default_factory=list)


@dataclass
class ScannedCLI:
    program: str = ""
    version: str = ""
    description: str = ""
    usage: str = ""
    flags: list[Flag] = field(default_factory=list)
    subcommands: list[Subcommand] = field(default_factory=list)
    raw_help: str = ""
    help_lines: int = 0


# ── Regex patterns for common CLI help formats ──

# GNU-style: -f, --flag ARG    Description
# Args only match: <arg>, [arg], or ALL_CAPS (e.g., FILE, N)
_RE_FLAG_GNU = re.compile(
    r"^\s{1,8}"                          # leading whitespace (1+ spaces)
    r"(?:(-\w),?\s*)?"                   # optional short: -f
    r"(--[\w][\w\-]*)"                   # long: --flag
    r"(?:"
    r"[=\s]+<([\w:.\-]+)>"              # <arg> style
    r"|[=\s]+\[([\w:.\-]+)\]"           # [arg] style
    r"|[=\s]+([A-Z][A-Z_\-]+)"          # ALL_CAPS style
    r")?",
    re.MULTILINE,
)

# Short-only flags: -f ARG   Description
_RE_FLAG_SHORT = re.compile(
    r"^\s{2,8}"
    r"(-\w)"
    r"(?:\s+([A-Z][\w\-]*))?",
    re.MULTILINE,
)

# Subcommand line:   command   Description
_RE_SUBCOMMAND = re.compile(
    r"^\s{2,8}([\w][\w\-]*)\s{2,}(.+)$",
    re.MULTILINE,
)


def capture_help(program: str, args: list[str] = None,
                 timeout: int = 10) -> Optional[str]:
    """Run program with --help and capture output.

    Only reads output — never executes the program's main functionality.
    """
    cmd = program.split() if isinstance(program, str) else list(program)
    if args:
        cmd.extend(args)
    if "--help" not in cmd and "-h" not in cmd:
        cmd.append("--help")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Some programs print help to stderr
        output = result.stdout or result.stderr
        return output.strip() if output else None
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return None


def parse_help(text: str, program_name: str = "") -> ScannedCLI:
    """Parse --help output into structured ScannedCLI."""
    cli = ScannedCLI(
        program=program_name,
        raw_help=text,
        help_lines=len(text.splitlines()),
    )

    lines = text.splitlines()

    # Extract description (usually first non-empty, non-usage line)
    for line in lines[:10]:
        line = line.strip()
        if line and not line.lower().startswith(("usage:", "options:", "commands:")):
            if not line.startswith("-") and len(line) > 10:
                cli.description = line
                break

    # Extract usage line
    for line in lines[:15]:
        if line.strip().lower().startswith("usage:"):
            cli.usage = line.strip()
            break

    # Extract version
    version_match = re.search(r"(?:version|v)[\s:]*(\d+\.\d+[\.\d]*)", text, re.IGNORECASE)
    if version_match:
        cli.version = version_match.group(1)

    # Parse flags
    cli.flags = _parse_flags(text)

    # Parse subcommands
    cli.subcommands = _parse_subcommands(text)

    return cli


def _parse_flags(text: str) -> list[Flag]:
    """Extract flags from help text.

    Handles:
    - GNU-style:  -f, --flag ARG    Description
    - Compact:    --flag=VALUE       Description
    - Usage-line: [-f | --flag] extracted from usage: lines
    - Indented:   -f, --flag         Description (Click/Cobra)
    """
    flags = []
    seen = set()
    lines = text.splitlines()

    # Pass 1: Extract from usage line (e.g. git)
    usage_flags = re.findall(r'\[(-\w)\s*\|\s*(--[\w-]+)\]', text)
    for short, long in usage_flags:
        key = long or short
        if key not in seen:
            seen.add(key)
            flags.append(Flag(short=short, long=long))

    # Also extract [--flag=<arg>] patterns
    usage_long = re.findall(r'\[(--[\w-]+)(?:\[?=<([\w-]+)>\]?)?\]', text)
    for long, arg in usage_long:
        if long not in seen:
            seen.add(long)
            flags.append(Flag(long=long, arg=arg))

    # Pass 2: Extract from ALL indented flag lines throughout the text
    # This catches formats like curl (flags right after usage) and
    # standard options sections
    for line in lines:
        # Skip non-indented lines and section headers
        if not line.startswith(" "):
            continue
        stripped = line.strip()
        if stripped.endswith(":") and len(stripped) < 40:
            continue

        # Try GNU-style: -f, --flag ARG   Description
        match = _RE_FLAG_GNU.search(line)
        if match:
            short = match.group(1) or ""
            long = match.group(2)
            # arg can be in group 3 (<arg>), 4 ([arg]), or 5 (ALL_CAPS)
            arg = match.group(3) or match.group(4) or match.group(5) or ""
            key = long or short
            if key and key not in seen:
                seen.add(key)
                desc = line[match.end():].strip().lstrip("- ").strip()
                flags.append(Flag(short=short, long=long, arg=arg, description=desc))
            continue

        # Try short-with-long: " -f, --flag <arg>   desc" (curl-style)
        short_long = re.match(
            r"^\s+(-\w),\s+(--[\w-]+)\s+(?:<([\w:.-]+)>)?\s*(.*)",
            line,
        )
        if short_long:
            short = short_long.group(1)
            long = short_long.group(2)
            arg = short_long.group(3) or ""
            desc = short_long.group(4).strip()
            key = long
            if key not in seen:
                seen.add(key)
                flags.append(Flag(short=short, long=long, arg=arg, description=desc))

    return flags


def _parse_subcommands(text: str) -> list[Subcommand]:
    """Extract subcommands from help text.

    Handles multiple formats:
    - Standard: "Commands:" section followed by indented "name  desc" lines
    - Git-style: section headers without colon, indented "name  desc" lines
    - Click/Cobra: "Commands:" or "Available Commands:" sections
    """
    subcommands = []
    seen = set()
    lines = text.splitlines()

    # Keywords that indicate a commands section
    _section_triggers = {
        "commands:", "available commands:", "subcommands:",
        "positional arguments:", "commands",
    }

    # Keywords that indicate we're past the commands section
    _stop_words = {"options:", "flags:", "global options:", "environment:",
                   "examples:", "see ", "learn more", "for more"}

    in_commands_section = False
    blank_count = 0

    for line in lines:
        stripped = line.strip().lower()

        # Detect command section headers (with or without colon)
        if stripped in _section_triggers:
            in_commands_section = True
            blank_count = 0
            continue

        # Git-style headers: lines that are NOT indented and describe a category
        # e.g. "start a working area (see also: git help tutorial)"
        if (not line.startswith(" ") and stripped and
                "(" in stripped and "see" in stripped):
            in_commands_section = True
            blank_count = 0
            continue

        # Non-indented descriptive headers (git-style category labels)
        if (not line.startswith(" ") and stripped and
                not stripped.startswith("-") and
                len(stripped.split()) >= 3 and
                not any(stripped.startswith(s) for s in _stop_words)):
            # Could be a git-style section header like "grow, mark and tweak..."
            if in_commands_section:
                blank_count = 0
                continue

        if in_commands_section:
            if not stripped:
                blank_count += 1
                if blank_count > 2:
                    in_commands_section = False
                continue

            # Stop on non-command sections
            if any(stripped.startswith(s) for s in _stop_words):
                in_commands_section = False
                continue

            blank_count = 0

            match = _RE_SUBCOMMAND.match(line)
            if match:
                name, desc = match.group(1), match.group(2).strip()
                if name not in seen and not name.startswith("-"):
                    seen.add(name)
                    subcommands.append(Subcommand(name=name, description=desc))

    return subcommands


def scan_recursive(program: str, max_depth: int = 2,
                   timeout: int = 10) -> ScannedCLI:
    """Scan program and its subcommands recursively.

    Depth-limited to avoid infinite recursion (default: 2 levels).
    """
    help_text = capture_help(program, timeout=timeout)
    if not help_text:
        return ScannedCLI(program=program)

    cli = parse_help(help_text, program_name=program.split()[0])

    if max_depth > 0 and cli.subcommands:
        for sub in cli.subcommands[:20]:  # limit to 20 subcommands
            sub_help = capture_help(f"{program} {sub.name}", timeout=timeout)
            if sub_help:
                sub_parsed = parse_help(sub_help, f"{program} {sub.name}")
                sub.flags = sub_parsed.flags
                if max_depth > 1:
                    sub.subcommands = [
                        Subcommand(name=s.name, description=s.description)
                        for s in sub_parsed.subcommands[:10]
                    ]

    return cli


def format_summary(cli: ScannedCLI) -> str:
    """Format ScannedCLI as markdown summary for .seif module."""
    parts = []

    # Header
    parts.append(f"## {cli.program} — CLI Knowledge Base")
    if cli.version:
        parts.append(f"Version: {cli.version}")
    if cli.description:
        parts.append(f"\n{cli.description}")
    if cli.usage:
        parts.append(f"\n`{cli.usage}`")

    # Global flags
    if cli.flags:
        parts.append(f"\n### Global Flags ({len(cli.flags)})")
        for f in cli.flags[:50]:
            flag_str = ""
            if f.short:
                flag_str += f.short
            if f.long:
                flag_str += (", " if f.short else "") + f.long
            if f.arg:
                flag_str += f" {f.arg}"
            desc = f" — {f.description}" if f.description else ""
            parts.append(f"- `{flag_str}`{desc}")

    # Subcommands
    if cli.subcommands:
        parts.append(f"\n### Subcommands ({len(cli.subcommands)})")
        for sub in cli.subcommands:
            parts.append(f"\n#### {cli.program} {sub.name}")
            if sub.description:
                parts.append(sub.description)
            if sub.flags:
                for f in sub.flags[:20]:
                    flag_str = ""
                    if f.short:
                        flag_str += f.short
                    if f.long:
                        flag_str += (", " if f.short else "") + f.long
                    if f.arg:
                        flag_str += f" {f.arg}"
                    desc = f" — {f.description}" if f.description else ""
                    parts.append(f"  - `{flag_str}`{desc}")
            if sub.subcommands:
                for nested in sub.subcommands[:10]:
                    parts.append(f"  - **{nested.name}**: {nested.description}")

    # Stats
    parts.append(f"\n### Stats")
    parts.append(f"- Help output: {cli.help_lines} lines")
    parts.append(f"- Global flags: {len(cli.flags)}")
    parts.append(f"- Subcommands: {len(cli.subcommands)}")
    total_sub_flags = sum(len(s.flags) for s in cli.subcommands)
    if total_sub_flags:
        parts.append(f"- Subcommand flags: {total_sub_flags}")

    return "\n".join(parts)


def scan_program(program: str, max_depth: int = 2,
                 target_path: str = None,
                 global_store: bool = False,
                 author: str = "cli-scanner",
                 timeout: int = 10) -> tuple:
    """Scan a CLI program and generate a .seif knowledge module.

    Args:
        program: Program name or command (e.g., "docker", "ffmpeg")
        max_depth: Recursion depth for subcommands (default: 2)
        target_path: Override output path
        global_store: If True, save to ~/.seif/ instead of ./.seif/
        author: Provenance author
        timeout: Timeout per --help call in seconds

    Returns:
        Tuple of (SeifModule, Path) or (None, None) on failure.
    """
    from seif.context.context_manager import create_module, save_module

    # Scan
    cli = scan_recursive(program, max_depth=max_depth, timeout=timeout)

    if not cli.raw_help:
        return None, None

    # Format
    summary = format_summary(cli)

    # Create module
    module = create_module(
        source_name=f"{cli.program} (cli-scanned)",
        original_words=len(cli.raw_help.split()),
        summary=summary,
        author=author,
        via="seif-scan",
    )
    module.classification = "PUBLIC"  # CLI help is always public

    # Determine save path
    if target_path:
        save_path = Path(target_path)
    elif global_store:
        global_dir = Path.home() / ".seif" / "tools"
        global_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^\w\-]', '_', cli.program)
        save_path = global_dir / f"{safe_name}.seif"
    else:
        save_path = None  # use default .seif/ location

    path = save_module(module, target_path=save_path)

    return module, path
