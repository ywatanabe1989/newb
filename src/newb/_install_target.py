"""Resolve a target repo (``<owner>/<repo>``) for ``newb install`` etc.

The single-repo install verbs (``newb scaffold-workflow``,
``newb set-secret``, ``newb install``) accept either:

* an explicit ``<owner>/<repo>`` positional, or
* ``.``, or no positional at all — both mean "current git remote".

This module owns that resolution. It deliberately does NOT know
anything about ecosystems; ecosystem-wide loops live in scitex-dev,
which calls newb once per repo.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


# GitHub-y owner/repo shape: alphanumerics, dashes, dots, underscores.
# Owner can't start with `-`. Repo can be `_xyz`. Length caps are
# permissive — GitHub enforces stricter rules, we just want a sanity
# guard against accidental paths.
_OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,38}/[A-Za-z0-9._\-]{1,100}$")

# git remote URL → (owner, repo). Handles:
#   git@github.com:owner/repo.git
#   https://github.com/owner/repo.git
#   https://github.com/owner/repo
_GIT_REMOTE_RE = re.compile(
    r"github\.com[:/]+(?P<owner>[A-Za-z0-9][A-Za-z0-9\-]+)/(?P<repo>[A-Za-z0-9._\-]+?)(?:\.git)?/?$"
)


def resolve_target(spec: Optional[str], cwd: Optional[Path] = None) -> str:
    """Resolve the repo spec to a normalized ``<owner>/<repo>``.

    ``spec`` of ``None`` or ``"."`` means "read the current git
    repo's ``origin`` URL". Anything else is parsed as
    ``<owner>/<repo>`` and validated against the GitHub naming shape.

    Raises ``ValueError`` with a short, actionable message on failure.
    """
    if spec is None or spec == ".":
        return _from_git_remote(cwd or Path.cwd())
    if not _OWNER_REPO_RE.match(spec):
        raise ValueError(
            f"target {spec!r} is not in <owner>/<repo> shape (e.g. ywatanabe1989/newb)"
        )
    return spec


def _from_git_remote(cwd: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ValueError(
            f"no git remote.origin.url under {cwd} — pass an explicit "
            f"<owner>/<repo> argument instead"
        )
    url = proc.stdout.strip()
    m = _GIT_REMOTE_RE.search(url)
    if not m:
        raise ValueError(
            f"git remote {url!r} doesn't look like a GitHub URL — "
            f"pass an explicit <owner>/<repo>"
        )
    return f"{m['owner']}/{m['repo']}"


# EOF
