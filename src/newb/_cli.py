"""newb CLI — ``newb <skills_dir>``.

newb 0.6.0 delegates ALL runtime/auth/isolation/lifecycle to
scitex-agent-container (sac). The CLI surface is therefore minimal:
just the source, model, output format, and the host sac will run the
agent on. Everything else is sac-internal.
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
    type=click.Choice(["docker", "apptainer"]),
    default="docker",
    help="Container the agent runs in. "
    "docker=ghcr.io/ywatanabe1989/newb-runner (hard isolation, default); "
    "apptainer=same image via apptainer (HPC). "
    "host runtime was removed in 0.9 — container is the boundary.",
)
@click.version_option()
@click.pass_context
def main(ctx, source, model, runs, out_format, runtime):
    """Run a fresh AI agent against a docs/skills directory or git URL.

    \b
    SOURCE may be:
      - a local directory containing .md files (any layout)
      - a git URL (https://, git@, or *.git) — shallow-cloned, then
        _skills/, docs/, or repo root is auto-detected.

    \b
    Backed by Anthropic's claude-agent-sdk:
      No docker, no multiplexer, no wire format. The SDK handles the
      Claude Code session; newb owns the test schema + grading.

    \b
    Auth (NEWB_-prefixed env vars only — no upstream surprises):
      $ export NEWB_ANTHROPIC_API_KEY=sk-ant-api03-...   # canonical, ToS-clean
      (Or rely on your local ~/.claude/ OAuth login on personal machines —
       newb actively masks any stray ANTHROPIC_API_KEY so it can't sneak in.)

    \b
    Example:
        $ newb ./docs
        $ newb ./src/mypkg/_skills/mypkg
        $ newb https://github.com/user/repo.git
        $ newb ./docs --format markdown >> README.md
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
