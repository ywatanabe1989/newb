"""Project-root staging — shared by all isolation runtimes.

Stages the project's install location (the dir containing ``.git`` or
``pyproject.toml``) into a tmp dir for the agent's cwd. Respects the
project's ``.gitignore`` when it's a git repo (``git ls-files --cached
--others --exclude-standard``); falls back to a hardcoded ignore list
plus broken-symlink skipping otherwise.

This is the single source of truth for what enters a staged copy.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Hardcoded essentials — only the things that MUST never enter a
# staged copy regardless of .gitignore: VCS internals, local venvs,
# bytecode caches, agent state with broken symlinks. The project's
# own .gitignore decides everything else.
_STAGE_HARDCODED_IGNORE = shutil.ignore_patterns(
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "*.pyc",
    ".claude",
)


def _stage_ignore_fallback(src: str, names: list[str]) -> set[str]:
    """Pattern ignore + skip broken symlinks (used when not a git repo)."""
    skipped = set(_STAGE_HARDCODED_IGNORE(src, names))
    src_path = Path(src)
    for name in names:
        if name in skipped:
            continue
        p = src_path / name
        if p.is_symlink():
            try:
                if not p.resolve(strict=True).exists():
                    skipped.add(name)
            except (OSError, RuntimeError):
                skipped.add(name)
    return skipped


def stage_project(src: Path, dst: Path) -> None:
    """Stage ``src`` under ``dst``, respecting the project's .gitignore.

    For git repos: uses ``git ls-files --cached --others
    --exclude-standard`` to get the set the user considers part of the
    project (tracked + untracked-but-not-ignored). Falls back to
    ``shutil.copytree`` with hardcoded essentials when not a git repo.
    """
    import subprocess as _sp

    src = src.resolve()
    if (src / ".git").exists():
        try:
            out = _sp.run(
                [
                    "git",
                    "-C",
                    str(src),
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            files = [line for line in out.stdout.splitlines() if line]
            dst.mkdir(parents=True, exist_ok=True)
            for rel in files:
                src_file = src / rel
                if not src_file.exists():  # broken symlink or already gone
                    continue
                if src_file.is_symlink():
                    try:
                        if not src_file.resolve(strict=True).exists():
                            continue
                    except (OSError, RuntimeError):
                        continue
                dst_file = dst / rel
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(src_file, dst_file, follow_symlinks=True)
                except (OSError, shutil.SameFileError):
                    continue
            return
        except (_sp.CalledProcessError, FileNotFoundError):
            pass  # fall through to copytree
    shutil.copytree(src, dst, ignore=_stage_ignore_fallback)
