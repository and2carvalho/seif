"""
Git Hooks Installer — Auto-sync .seif on git events.

Installs lightweight git hooks that run `seif --sync` automatically:
  - post-commit: after you commit → context updated
  - post-merge:  after git pull  → new code arrived
  - post-checkout: after branch switch → different context

The hooks are non-blocking (run in background) and fail silently.
They do NOT interfere with existing hooks (appends, doesn't replace).

Usage:
  seif --install-hooks              # install in current repo
  seif --install-hooks /path       # install in specific repo
"""

from pathlib import Path

HOOK_SCRIPT = '''#!/bin/sh
# S.E.I.F. auto-sync — keeps .seif/project.seif up to date
# Runs in background, fails silently, never blocks git operations
if command -v seif > /dev/null 2>&1; then
    seif --sync . --author "git-hook" --via "{hook_name}" > /dev/null 2>&1 &
fi
'''

HOOKS_TO_INSTALL = ["post-commit", "post-merge", "post-checkout"]

SEIF_MARKER = "# S.E.I.F. auto-sync"


def install_hooks(repo_path: str = ".") -> list[str]:
    """Install SEIF auto-sync git hooks in a repository.

    Non-destructive: if a hook already exists, appends the SEIF sync.
    If SEIF hook is already installed, skips.

    Args:
        repo_path: Path to the git repository.

    Returns:
        List of installed/updated hook names.
    """
    repo = Path(repo_path).resolve()
    hooks_dir = repo / ".git" / "hooks"

    if not hooks_dir.exists():
        return []

    installed = []

    for hook_name in HOOKS_TO_INSTALL:
        hook_path = hooks_dir / hook_name
        hook_content = HOOK_SCRIPT.format(hook_name=hook_name)

        if hook_path.exists():
            existing = hook_path.read_text()

            # Already installed — skip
            if SEIF_MARKER in existing:
                installed.append(f"{hook_name} (already installed)")
                continue

            # Append to existing hook
            with open(hook_path, "a") as f:
                f.write(f"\n{hook_content}")
            installed.append(f"{hook_name} (appended)")
        else:
            # Create new hook
            hook_path.write_text(f"#!/bin/sh\n{hook_content}")
            installed.append(f"{hook_name} (created)")

        # Ensure executable
        hook_path.chmod(0o755)

    return installed


def uninstall_hooks(repo_path: str = ".") -> list[str]:
    """Remove SEIF auto-sync from git hooks.

    Only removes the SEIF section, preserves other hook content.

    Returns:
        List of cleaned hook names.
    """
    repo = Path(repo_path).resolve()
    hooks_dir = repo / ".git" / "hooks"

    if not hooks_dir.exists():
        return []

    cleaned = []

    for hook_name in HOOKS_TO_INSTALL:
        hook_path = hooks_dir / hook_name

        if not hook_path.exists():
            continue

        content = hook_path.read_text()
        if SEIF_MARKER not in content:
            continue

        # Remove SEIF block (from marker to next empty line or EOF)
        lines = content.split("\n")
        new_lines = []
        skip = False
        for line in lines:
            if SEIF_MARKER in line:
                skip = True
                continue
            if skip and line.strip() == "":
                skip = False
                continue
            if skip and line.startswith("if ") or line.startswith("    seif ") or line.startswith("    seif-cli") or line.startswith("fi"):
                continue
            skip = False
            new_lines.append(line)

        remaining = "\n".join(new_lines).strip()
        if remaining == "#!/bin/sh" or not remaining:
            hook_path.unlink()
            cleaned.append(f"{hook_name} (removed)")
        else:
            hook_path.write_text(remaining + "\n")
            cleaned.append(f"{hook_name} (cleaned)")

    return cleaned


def check_hooks(repo_path: str = ".") -> dict:
    """Check which SEIF hooks are installed.

    Returns:
        Dict with hook status: {hook_name: "installed" | "not installed" | "no git"}
    """
    repo = Path(repo_path).resolve()
    hooks_dir = repo / ".git" / "hooks"

    if not hooks_dir.exists():
        return {h: "no git repo" for h in HOOKS_TO_INSTALL}

    status = {}
    for hook_name in HOOKS_TO_INSTALL:
        hook_path = hooks_dir / hook_name
        if hook_path.exists() and SEIF_MARKER in hook_path.read_text():
            status[hook_name] = "installed"
        else:
            status[hook_name] = "not installed"

    return status
