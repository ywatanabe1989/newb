"""newb CLI — ``newb <source>``.

The CLI is intentionally minimal: source, model, output format,
container runtime, question template. Everything else (auth,
isolation, lifecycle) is delegated to the chosen runtime.
"""

from __future__ import annotations

import json

import click

from ._verify import render_markdown
from ._verify import run as _run_impl
from .question_templates import DEFAULT_TEMPLATE, TEMPLATES


def _print_help_recursive(ctx: click.Context, _param, value):
    """Flatten help for the top command + every subcommand."""
    if not value or ctx.resilient_parsing:
        return
    cmd = ctx.command
    click.echo(cmd.get_help(ctx))
    if isinstance(cmd, click.Group):
        for name in sorted(cmd.commands):
            sub = cmd.commands[name]
            sub_ctx = click.Context(sub, info_name=name, parent=ctx)
            click.echo("\n---\n")
            click.echo(sub.get_help(sub_ctx))
    ctx.exit(0)


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--help-recursive",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_help_recursive,
    help="Flatten help for every subcommand.",
)
@click.version_option(prog_name="newb")
@click.pass_context
def main(ctx: click.Context):
    """Test your package through the eyes of a fresh AI agent.

    \b
    Example:
        $ newb verify .
        $ newb verify https://github.com/user/repo.git --format markdown
        $ newb templates list

    A sandboxed container session reads your project (respecting
    .gitignore) and answers four canonical questions about it.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


# ---------------------------------------------------------------------------
# verify — the main subcommand
# ---------------------------------------------------------------------------


@main.command()
@click.argument("source", required=True)
@click.option("--model", default="claude-haiku-4-5", help="Claude model id.")
@click.option("--runs", default=1, type=int, help="Runs per prompt.")
@click.option(
    "--template",
    type=click.Choice(sorted(TEMPLATES)),
    default=DEFAULT_TEMPLATE,
    help="Question template — which prompt set to send the agent.",
)
@click.option(
    "--format",
    "out_format",
    type=click.Choice(["json", "markdown"]),
    default="json",
    help="Output format.",
)
@click.option(
    "--json",
    "json_alias",
    is_flag=True,
    default=False,
    help="Alias for --format json (universal SciTeX flag).",
)
@click.option(
    "--runtime",
    type=click.Choice(["docker", "apptainer"]),
    default="docker",
    help="Container runtime. docker (default) or apptainer (HPC).",
)
def verify(source, model, runs, template, out_format, json_alias, runtime):
    """Run the agent against SOURCE — the main verify command.

    \b
    SOURCE may be:
      - a local directory containing .md files (any layout)
      - a git URL (https://, git@, or *.git) — shallow-cloned, then
        _skills/, docs/, or repo root is auto-detected.

    \b
    Auth (NEWB_-prefixed env vars only — no upstream surprises):
      $ export NEWB_ANTHROPIC_API_KEY=sk-ant-api03-...
      (or NEWB_ANTHROPIC_API_KEY_OAUTH=sk-ant-oat01-... for Pro/Max
       users with a Claude Code subscription — extracted from
       ~/.claude/.credentials.json)

    \b
    Example:
        $ newb verify .
        $ newb verify ./src/mypkg/_skills/mypkg
        $ newb verify https://github.com/user/repo.git
        $ newb verify . --template python-package --json
    """
    if json_alias:
        out_format = "json"
    click.echo(f"\U0001f41d newb: probing {source} ...", err=True)
    result = _run_impl(
        source,
        model=model,
        runs_per_prompt=runs,
        runtime=runtime,
        template=template,
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


# ---------------------------------------------------------------------------
# templates — list / show built-in question templates
# ---------------------------------------------------------------------------


@main.group()
def templates():
    """Built-in question templates — what newb asks the agent."""


@templates.command("list")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output.",
)
def templates_list(as_json):
    """List all built-in question templates."""
    rows = [
        {"name": n, "questions": list(p.keys())} for n, p in sorted(TEMPLATES.items())
    ]
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    for r in rows:
        click.echo(f"{r['name']}  ({len(r['questions'])} questions)")
        for q in r["questions"]:
            click.echo(f"  - {q}")


@templates.command("show")
@click.argument("name")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output.",
)
def templates_show(name, as_json):
    """Show the prompts in a template."""
    if name not in TEMPLATES:
        raise click.ClickException(
            f"unknown template {name!r}; available: {sorted(TEMPLATES)}"
        )
    prompts = TEMPLATES[name]
    if as_json:
        click.echo(json.dumps({"name": name, "prompts": prompts}, indent=2))
        return
    for k, prompt in prompts.items():
        click.echo(f"## {k}\n")
        click.echo(prompt)
        click.echo()


# ---------------------------------------------------------------------------
# Backward-compat shim — `newb <source>` (without `verify`) → `newb verify <source>`
# ---------------------------------------------------------------------------


_LEGACY_FLAGS = {
    "--model",
    "--runs",
    "--format",
    "--runtime",
    "--template",
    "--json",
    "-h",
    "--help",
}


def _legacy_dispatch():
    """If invoked as ``newb <SOURCE> ...`` (positional arg, no subcommand),
    rewrite argv as ``newb verify <SOURCE> ...`` so old call sites keep
    working.
    """
    import sys

    argv = sys.argv[1:]
    if not argv:
        return
    first = argv[0]
    # If first arg is a known subcommand or starts with a flag/help, no rewrite.
    if first in {"verify", "templates"} or first.startswith("-"):
        return
    sys.argv = [sys.argv[0], "verify"] + argv


if __name__ == "__main__":
    _legacy_dispatch()
    main()
else:
    # Also rewrite when invoked through the entry-point script.
    _legacy_dispatch()
