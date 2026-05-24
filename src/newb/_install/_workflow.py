"""``newb scaffold-workflow`` / ``set-secret`` / ``install`` — single repo.

Single-repo verbs only. No ecosystem awareness; multi-repo loops live
in scitex-dev (which consumes newb).

The CI workflow we drop is the same template documented in
``docs/badge.md``. The runner image
``ghcr.io/ywatanabe1989/newb-runner`` is public, so adopting repos
need one of two secrets — set exactly one:

  * ``NEWB_ANTHROPIC_API_KEY`` — real ``sk-ant-api*`` key, billed per
    token.
  * ``NEWB_CLAUDE_CODE_CREDENTIALS_JSON`` — full
    ``~/.claude/.credentials.json`` content for OAuth (Claude Code
    Pro / Max). Required for ``sk-ant-oat01-…`` tokens, which
    Anthropic rejects bare without refresh-token / expiresAt context.

The workflow forwards both env vars; the in-container runner picks
whichever is non-empty.
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
          # Set exactly one — API key for per-token billing, or the
          # full ~/.claude/.credentials.json content for OAuth
          # (Claude Code Pro / Max). See newb 30_env-vars docs.
          NEWB_ANTHROPIC_API_KEY: ${{ secrets.NEWB_ANTHROPIC_API_KEY }}
          NEWB_CLAUDE_CODE_CREDENTIALS_JSON: ${{ secrets.NEWB_CLAUDE_CODE_CREDENTIALS_JSON }}
          NEWB_HARDEN_MEMORY: 4g
          NEWB_HARDEN_PIDS_LIMIT: 512
          NEWB_HARDEN_CPUS: "2"
        run: |
          if [ -z "${NEWB_ANTHROPIC_API_KEY}" ] && [ -z "${NEWB_CLAUDE_CODE_CREDENTIALS_JSON}" ]; then
            echo "::error::Neither secrets.NEWB_ANTHROPIC_API_KEY nor secrets.NEWB_CLAUDE_CODE_CREDENTIALS_JSON is set on this repo." >&2
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


SECRET_API_KEY = "NEWB_ANTHROPIC_API_KEY"
SECRET_CREDS_JSON = "NEWB_CLAUDE_CODE_CREDENTIALS_JSON"


def secret_exists(target: str, name: str = SECRET_API_KEY, *, gh=None) -> bool:
    # ``gh`` is injectable so tests can supply a real fake callable
    # (no patching). Production callers leave it as ``None`` → use
    # the real ``_gh`` subprocess shim.
    if gh is None:
        gh = _gh
    try:
        out = gh("secret", "list", "--repo", target, "--json", "name")
    except GhError:
        return False
    return f'"{name}"' in out


def workflow_exists(target: str, *, gh=None) -> bool:
    """True iff `.github/workflows/newb.yml` is present on the default branch."""
    if gh is None:
        gh = _gh
    try:
        gh(
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


def set_secret(
    target: str,
    value: str,
    *,
    name: str = SECRET_API_KEY,
    force: bool = False,
    gh=None,
) -> str:
    """Set ``name`` (``NEWB_ANTHROPIC_API_KEY`` by default) on ``target``.

    Pass ``name=SECRET_CREDS_JSON`` and ``value`` = full
    ``~/.claude/.credentials.json`` content for the OAuth flat-rate path.

    Returns a short status string (``set`` / ``skip-existing``).
    """
    if gh is None:
        gh = _gh
    if not force and secret_exists(target, name, gh=gh):
        return "skip-existing"
    gh("secret", "set", name, "--repo", target, "--body", value)
    return "set"


def scaffold_workflow(
    target: str,
    *,
    push: bool = False,
    force: bool = False,
    gh=None,
) -> str:
    """Drop ``.github/workflows/newb.yml`` into ``target``.

    Default action: open a PR. ``push=True`` direct-pushes to default
    branch (faster, no review). Returns a status string.
    """
    if gh is None:
        gh = _gh
    if not force and workflow_exists(target, gh=gh):
        return "skip-existing"
    if push:
        return _scaffold_via_direct_push(target, gh=gh)
    return _scaffold_via_pr(target, gh=gh)


def _scaffold_via_pr(target: str, *, gh=None) -> str:
    """Clone, branch, write file, push branch, open PR."""
    if gh is None:
        gh = _gh
    workdir = Path(tempfile.mkdtemp(prefix="newb-install-"))
    try:
        repo_dir = workdir / "repo"
        gh("repo", "clone", target, str(repo_dir), "--", "--depth=1")
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
        out = gh(
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


def _scaffold_via_direct_push(target: str, *, gh=None) -> str:
    """Use the contents API to create the file on the default branch."""
    import base64

    if gh is None:
        gh = _gh
    encoded = base64.b64encode(WORKFLOW_BODY.encode()).decode()
    gh(
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
    secret_name: str = SECRET_API_KEY,
    push: bool = False,
    force: bool = False,
    gh=None,
) -> dict:
    """Combined: set secret + scaffold workflow.

    ``secret_value`` of ``None`` means "skip the secret step" (for
    repos where the org secret is already in scope, or a separate
    rotation flow handles it). ``secret_name`` selects which of the
    two newb auth secrets to populate — ``SECRET_API_KEY`` (default)
    or ``SECRET_CREDS_JSON`` for the OAuth flat-rate path.
    """
    out: dict = {}
    if secret_value is not None:
        out["secret"] = set_secret(
            target, secret_value, name=secret_name, force=force, gh=gh
        )
    else:
        out["secret"] = "skip-no-value"
    out["workflow"] = scaffold_workflow(target, push=push, force=force, gh=gh)
    return out


# EOF
