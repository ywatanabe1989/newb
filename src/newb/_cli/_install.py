"""``newb scaffold-workflow`` / ``set-secret`` / ``install`` Click verbs.

Single-repo verbs. Each accepts an optional positional
``<owner>/<repo>``; ``.`` or omitted means "current git remote".
Multi-repo loops live in scitex-dev (consumes newb).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click

from .._install._target import resolve_target
from .._install._workflow import (
    GhError,
    SECRET_API_KEY,
    SECRET_CREDS_JSON,
    install as _install,
    scaffold_workflow as _scaffold,
    set_secret as _set_secret,
)


def _resolve_or_die(target: str | None) -> str:
    try:
        return resolve_target(target)
    except ValueError as exc:
        click.echo(f"newb: {exc}", err=True)
        sys.exit(2)


def _read_secret_value() -> tuple[str, str]:
    """Resolve the auth secret to push to the repo.

    Resolution order (first non-empty wins):
      1. ``NEWB_CLAUDE_CODE_CREDENTIALS_JSON`` env var (full file contents).
      2. ``~/.claude/.credentials.json`` on disk (OAuth users' default).
      3. ``NEWB_ANTHROPIC_API_KEY`` env var (real ``sk-ant-api*`` keys).

    Returns ``(secret_name, value)``. Fails loudly if none are set.
    """
    creds_env = os.environ.get(SECRET_CREDS_JSON, "").strip()
    if creds_env:
        return SECRET_CREDS_JSON, creds_env
    creds_file = Path("~/.claude/.credentials.json").expanduser()
    if creds_file.is_file():
        return SECRET_CREDS_JSON, creds_file.read_text()
    api_key = os.environ.get(SECRET_API_KEY, "").strip()
    if api_key:
        return SECRET_API_KEY, api_key
    click.echo(
        f"newb: no auth source available — set {SECRET_API_KEY} or "
        f"{SECRET_CREDS_JSON}, or place ~/.claude/.credentials.json.",
        err=True,
    )
    sys.exit(2)


_DRY_RUN_HELP = "Print what would happen without making any remote changes."
_YES_HELP = "Skip the interactive confirmation prompt."


@click.command("scaffold-workflow")
@click.argument("target", required=False)
@click.option(
    "--push",
    is_flag=True,
    default=False,
    help="Direct-push to default branch instead of opening a PR.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite an existing newb.yml workflow.",
)
@click.option("--dry-run", is_flag=True, default=False, help=_DRY_RUN_HELP)
@click.option("--yes", "-y", is_flag=True, default=False, help=_YES_HELP)
def scaffold_workflow(
    target: str | None, push: bool, force: bool, dry_run: bool, yes: bool
):
    """Drop .github/workflows/newb.yml into TARGET.

    \b
    Example:
      $ newb dev scaffold-workflow owner/repo            # open a PR
      $ newb dev scaffold-workflow owner/repo --push     # direct-push
      $ newb dev scaffold-workflow .                     # current git remote
      $ newb dev scaffold-workflow owner/repo --dry-run  # preview only

    TARGET = <owner>/<repo>; '.' or omitted = current git remote.
    """
    repo = _resolve_or_die(target)
    if dry_run:
        click.echo(
            f"{repo}: dry-run — would write .github/workflows/newb.yml "
            f"({'direct-push' if push else 'PR'})"
        )
        return
    if not yes:
        click.echo(
            f"refusing to mutate {repo} without --yes/-y "
            "(or use --dry-run to preview).",
            err=True,
        )
        sys.exit(1)
    try:
        status = _scaffold(repo, push=push, force=force)
    except GhError as exc:
        click.echo(f"newb dev scaffold-workflow ({repo}): {exc}", err=True)
        sys.exit(1)
    click.echo(f"{repo}: workflow {status}")


@click.command("set-secret")
@click.argument("target", required=False)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite an existing secret.",
)
def set_secret(target: str | None, force: bool):
    """Set the newb auth secret on TARGET.

    \b
    Example:
      # API-key path (per-token billing)
      $ export NEWB_ANTHROPIC_API_KEY=sk-ant-api03-...
      $ newb dev set-secret owner/repo

      # OAuth flat-rate path (Claude Code Pro / Max). Auto-detected
      # from ~/.claude/.credentials.json or NEWB_CLAUDE_CODE_CREDENTIALS_JSON.
      $ newb dev set-secret owner/repo

    TARGET = <owner>/<repo>; '.' or omitted = current git remote.
    Picks NEWB_CLAUDE_CODE_CREDENTIALS_JSON if either the env var
    or ~/.claude/.credentials.json is available; otherwise falls
    back to NEWB_ANTHROPIC_API_KEY from the host env.
    """
    repo = _resolve_or_die(target)
    name, value = _read_secret_value()
    try:
        status = _set_secret(repo, value, name=name, force=force)
    except GhError as exc:
        click.echo(f"newb dev set-secret ({repo}): {exc}", err=True)
        sys.exit(1)
    click.echo(f"{repo}: secret {name} {status}")


@click.command("install")
@click.argument("target", required=False)
@click.option(
    "--push",
    is_flag=True,
    default=False,
    help="Direct-push the workflow instead of opening a PR.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite an existing secret AND workflow.",
)
@click.option(
    "--no-secret",
    is_flag=True,
    default=False,
    help="Skip the secret step (e.g. if an org-level secret is already in scope).",
)
@click.option("--dry-run", is_flag=True, default=False, help=_DRY_RUN_HELP)
@click.option("--yes", "-y", is_flag=True, default=False, help=_YES_HELP)
def install(
    target: str | None,
    push: bool,
    force: bool,
    no_secret: bool,
    dry_run: bool,
    yes: bool,
):
    """Install newb CI on TARGET = scaffold-workflow + set-secret.

    \b
    Example:
      $ export NEWB_ANTHROPIC_API_KEY=sk-ant-...
      $ newb dev install owner/repo            # PR + secret
      $ newb dev install owner/repo --push     # direct-push + secret
      $ newb dev install . --no-secret         # workflow only
      $ newb dev install owner/repo --dry-run  # preview

    TARGET = <owner>/<repo>; '.' or omitted = current git remote.
    An auth source (NEWB_ANTHROPIC_API_KEY,
    NEWB_CLAUDE_CODE_CREDENTIALS_JSON, or ~/.claude/.credentials.json)
    is required unless --no-secret.
    """
    repo = _resolve_or_die(target)
    name: str = SECRET_API_KEY
    value: str | None = None
    if not no_secret:
        name, value = _read_secret_value()
    if dry_run:
        secret_part = "skip-no-value" if value is None else f"would-set {name}"
        click.echo(
            f"{repo}: dry-run — secret {secret_part}, workflow "
            f"would-{'push' if push else 'pr'}"
        )
        return
    if not yes:
        click.echo(
            f"refusing to mutate {repo} without --yes/-y "
            "(or use --dry-run to preview).",
            err=True,
        )
        sys.exit(1)
    try:
        out = _install(
            repo,
            secret_value=value,
            secret_name=name,
            push=push,
            force=force,
        )
    except GhError as exc:
        click.echo(f"newb dev install ({repo}): {exc}", err=True)
        sys.exit(1)
    click.echo(f"{repo}: secret {out['secret']}, workflow {out['workflow']}")


# EOF
