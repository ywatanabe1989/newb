"""``newb scaffold-workflow`` / ``set-secret`` / ``install`` Click verbs.

Single-repo verbs. Each accepts an optional positional
``<owner>/<repo>``; ``.`` or omitted means "current git remote".
Multi-repo loops live in scitex-dev (consumes newb).
"""

from __future__ import annotations

import os
import sys

import click

from .._install._target import resolve_target
from .._install._workflow import (
    GhError,
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


def _read_secret_value() -> str:
    """Read NEWB_ANTHROPIC_API_KEY from env; fail loudly if missing."""
    v = os.environ.get("NEWB_ANTHROPIC_API_KEY", "").strip()
    if not v:
        click.echo(
            "newb: NEWB_ANTHROPIC_API_KEY env var is empty — set it "
            "before running set-secret / install.",
            err=True,
        )
        sys.exit(2)
    return v


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
    """Set NEWB_ANTHROPIC_API_KEY on TARGET.

    \b
    Example:
      $ export NEWB_ANTHROPIC_API_KEY=sk-ant-...
      $ newb dev set-secret owner/repo
      $ newb dev set-secret .                  # current git remote
      $ newb dev set-secret owner/repo --force # overwrite

    TARGET = <owner>/<repo>; '.' or omitted = current git remote.
    Reads the value from the host's NEWB_ANTHROPIC_API_KEY env var.
    """
    repo = _resolve_or_die(target)
    value = _read_secret_value()
    try:
        status = _set_secret(repo, value, force=force)
    except GhError as exc:
        click.echo(f"newb dev set-secret ({repo}): {exc}", err=True)
        sys.exit(1)
    click.echo(f"{repo}: secret {status}")


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
    NEWB_ANTHROPIC_API_KEY env var is required unless --no-secret.
    """
    repo = _resolve_or_die(target)
    value = None if no_secret else _read_secret_value()
    if dry_run:
        secret_part = "skip-no-value" if value is None else "would-set"
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
        out = _install(repo, secret_value=value, push=push, force=force)
    except GhError as exc:
        click.echo(f"newb dev install ({repo}): {exc}", err=True)
        sys.exit(1)
    click.echo(f"{repo}: secret {out['secret']}, workflow {out['workflow']}")


# EOF
