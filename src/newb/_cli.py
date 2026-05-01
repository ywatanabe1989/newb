"""newb CLI — ``newb <skills_dir>``.

Pytest-style: no subcommand. ``newb ./skills`` runs the agent the same
way ``pytest ./tests`` runs the test suite.
"""

from __future__ import annotations

import json

import click

from ._verify import render_markdown
from ._verify import run as _run_impl


@click.command()
@click.argument("source", required=False)
@click.option("--model", default="claude-haiku-4-5", help="Claude model id.")
@click.option("--runs", default=1, type=int, help="Runs per prompt.")
@click.option(
    "--format",
    "out_format",
    type=click.Choice(["json", "markdown"]),
    default="json",
    help="Output format.",
)
@click.option(
    "--runtime",
    type=click.Choice(["docker", "local", "apptainer"]),
    default="docker",
    help="Where to run the agent. local=host subprocess, docker=container, "
    "apptainer=HPC (planned).",
)
@click.option(
    "--claude-code-credential",
    "claude_code_credential",
    type=click.Path(dir_okay=False),
    default=None,
    help="Path to Claude Code credentials JSON (extracts OAuth token; "
    "uses subscription quota — $0 marginal). Env: $NEWB_CLAUDE_CODE_CREDENTIAL. "
    "PREFERRED over --api-key when both resolve.",
)
@click.option(
    "--api-key",
    "api_key",
    default=None,
    help="Direct Anthropic API token (sk-ant-api03-...). "
    "Env: $NEWB_ANTHROPIC_API_KEY. Per-call API spend.",
)
@click.option(
    "--config-dir",
    type=click.Path(file_okay=False),
    default=None,
    help="Explicit isolation HOME for --runtime=local (default: fresh tmp).",
)
@click.version_option()
@click.pass_context
def main(
    ctx,
    source,
    model,
    runs,
    out_format,
    runtime,
    claude_code_credential,
    api_key,
    config_dir,
):
    """Run a fresh AI agent against a docs/skills directory or git URL.

    \b
    SOURCE may be:
      - a local directory containing .md files (any layout)
      - a git URL (https://, git@, or *.git) — shallow-cloned, then
        _skills/, docs/, or repo root is auto-detected.

    \b
    Auth (--runtime=local; pick one — claude-code-credential wins if both):
      $ export NEWB_CLAUDE_CODE_CREDENTIAL=~/.claude/.credentials.json   # subscription
      $ export NEWB_ANTHROPIC_API_KEY=sk-ant-api03-...                   # per-call $

    \b
    Example:
        $ newb ./docs
        $ newb ./src/mypkg/_skills/mypkg
        $ newb https://github.com/user/repo.git
        $ newb ./docs --runtime local --claude-code-credential ~/.claude/.credentials.json
    """
    if source is None:
        click.echo(ctx.get_help())
        ctx.exit(0)
    click.echo(f"\U0001f41d newb: probing {source} ...", err=True)
    result = _run_impl(
        source,
        model=model,
        runs_per_prompt=runs,
        runtime=runtime,
        api_key=api_key,
        claude_code_credential=claude_code_credential,
        config_dir=config_dir,
    )
    if out_format == "markdown":
        click.echo(render_markdown(result), nl=False)
    else:
        click.echo(json.dumps(result, indent=2))
    summary = result.get("tests_summary")
    if summary:
        p, t = summary["passed"], summary["total"]
        emoji = (
            "\U0001f41d\u2705"
            if p == t
            else ("\U0001f41d\u26a0\ufe0f" if p > 0 else "\U0001f41d\u274c")
        )
        click.echo(f"{emoji} {p}/{t} tests passed", err=True)
    else:
        click.echo(
            "\U0001f41d smoke check complete (no tests_newb.yaml found)", err=True
        )


if __name__ == "__main__":
    main()
