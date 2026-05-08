"""``newb scaffold-workflow`` / ``set-secret`` / ``install`` — single repo.

Single-repo verbs only. No ecosystem awareness; multi-repo loops live
in scitex-dev (which consumes newb).

The CI workflow we drop is the same template documented in
``docs/badge.md``. The runner image
``ghcr.io/ywatanabe1989/newb-runner`` is public, so adopting repos
need exactly one secret: ``NEWB_ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


WORKFLOW_PATH = ".github/workflows/newb.yml"

# Source of truth for the workflow body. Keep in sync with the
# template shown in docs/badge.md (the docs is the user-facing copy;
# this is what we actually write into adopting repos).
WORKFLOW_BODY = """\
name: Newb

# A fresh AI agent reads this package's docs and tries to use the
# package. If it succeeds, the docs work. See
# https://github.com/ywatanabe1989/newb for details.

on:
  workflow_dispatch:

jobs:
  newb:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Install newb
        run: pip install --upgrade newb

      - name: Run newb
        env:
          NEWB_ANTHROPIC_API_KEY: ${{ secrets.NEWB_ANTHROPIC_API_KEY }}
          NEWB_HARDEN_MEMORY: 4g
          NEWB_HARDEN_PIDS_LIMIT: 512
          NEWB_HARDEN_CPUS: "2"
        run: |
          if [ -z "${NEWB_ANTHROPIC_API_KEY}" ]; then
            echo "::error::secrets.NEWB_ANTHROPIC_API_KEY is not set." >&2
            exit 1
          fi
          newb . --json -vv > newb-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: newb-report
          path: newb-report.json
          if-no-files-found: warn

      - name: Gate on report (optional — uncomment to hard-fail)
        # run: newb gate newb-report.json
        run: 'true'

      - name: Render markdown summary
        if: success()
        run: |
          python - <<'PY' >> "$GITHUB_STEP_SUMMARY"
          import json, newb
          with open("newb-report.json") as f:
              report = json.load(f)
          print(newb.render_markdown(report))
          PY
"""


# ---------------------------------------------------------------------------
# gh CLI surface — kept thin so tests can monkeypatch _gh()
# ---------------------------------------------------------------------------


class GhError(RuntimeError):
    """Raised when a `gh` invocation exits non-zero."""


def _gh(*args: str, input: Optional[str] = None) -> str:
    """Run `gh <args>` and return stdout. Raise GhError on non-zero."""
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        input=input,
    )
    if proc.returncode != 0:
        raise GhError(
            f"gh {' '.join(args)!r} failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def secret_exists(target: str) -> bool:
    try:
        out = _gh("secret", "list", "--repo", target, "--json", "name")
    except GhError:
        return False
    return '"NEWB_ANTHROPIC_API_KEY"' in out


def workflow_exists(target: str) -> bool:
    """True iff `.github/workflows/newb.yml` is present on the default branch."""
    try:
        _gh(
            "api",
            f"/repos/{target}/contents/{WORKFLOW_PATH}",
            "--silent",
        )
        return True
    except GhError:
        return False


# ---------------------------------------------------------------------------
# Verbs
# ---------------------------------------------------------------------------


def set_secret(target: str, value: str, *, force: bool = False) -> str:
    """Set ``NEWB_ANTHROPIC_API_KEY`` on ``target``.

    Returns a short status string (``set`` / ``skip-existing``).
    """
    if not force and secret_exists(target):
        return "skip-existing"
    _gh(
        "secret",
        "set",
        "NEWB_ANTHROPIC_API_KEY",
        "--repo",
        target,
        "--body",
        value,
    )
    return "set"


def scaffold_workflow(
    target: str,
    *,
    push: bool = False,
    force: bool = False,
) -> str:
    """Drop ``.github/workflows/newb.yml`` into ``target``.

    Default action: open a PR. ``push=True`` direct-pushes to default
    branch (faster, no review). Returns a status string.
    """
    if not force and workflow_exists(target):
        return "skip-existing"
    if push:
        return _scaffold_via_direct_push(target)
    return _scaffold_via_pr(target)


def _scaffold_via_pr(target: str) -> str:
    """Clone, branch, write file, push branch, open PR."""
    workdir = Path(tempfile.mkdtemp(prefix="newb-install-"))
    try:
        repo_dir = workdir / "repo"
        _gh("repo", "clone", target, str(repo_dir), "--", "--depth=1")
        wf = repo_dir / WORKFLOW_PATH
        wf.parent.mkdir(parents=True, exist_ok=True)
        wf.write_text(WORKFLOW_BODY)
        branch = "newb/install-workflow"
        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout", "-b", branch],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "add", WORKFLOW_PATH],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "commit", "-m", "ci: add newb workflow"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "push", "-u", "origin", branch],
            check=True,
            capture_output=True,
        )
        body = (
            "Adds the `Newb | passing` workflow. Generated by "
            "`newb scaffold-workflow`.\n\n"
            "Trigger once manually from the Actions tab to confirm "
            "the run is green, then add the badge to README per "
            "https://github.com/ywatanabe1989/newb/blob/main/docs/badge.md."
        )
        out = _gh(
            "pr",
            "create",
            "--repo",
            target,
            "--title",
            "ci: add newb workflow",
            "--body",
            body,
            "--head",
            branch,
        )
        return f"pr-opened: {out.strip().splitlines()[-1]}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _scaffold_via_direct_push(target: str) -> str:
    """Use the contents API to create the file on the default branch."""
    import base64

    encoded = base64.b64encode(WORKFLOW_BODY.encode()).decode()
    _gh(
        "api",
        "--method",
        "PUT",
        f"/repos/{target}/contents/{WORKFLOW_PATH}",
        "-f",
        "message=ci: add newb workflow",
        "-f",
        f"content={encoded}",
    )
    return "pushed"


def install(
    target: str,
    *,
    secret_value: Optional[str] = None,
    push: bool = False,
    force: bool = False,
) -> dict:
    """Combined: set secret + scaffold workflow.

    ``secret_value`` of ``None`` means "skip the secret step" (for
    repos where the org secret is already in scope, or a separate
    rotation flow handles it).
    """
    out: dict = {}
    if secret_value is not None:
        out["secret"] = set_secret(target, secret_value, force=force)
    else:
        out["secret"] = "skip-no-value"
    out["workflow"] = scaffold_workflow(target, push=push, force=force)
    return out


# EOF
