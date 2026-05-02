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
    """List all built-in question templates.

    \b
    Example:
      $ newb templates list
      $ newb templates list --json
    """
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
    """Show the prompts in a template.

    \b
    Example:
      $ newb templates show python-package
      $ newb templates show cli-tool --json
    """
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
# skills — list / get newb's own _skills/<pkg>/ tree (introspection parity
# with scitex packages' `<pkg> skills list/get`)
# ---------------------------------------------------------------------------


@main.group()
def skills():
    """newb's own agent-facing skill leaves (under src/newb/_skills/newb/)."""


def _skills_dir():
    from pathlib import Path

    import newb as _newb

    return Path(_newb.__file__).parent / "_skills" / "newb"


@skills.command("list")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output.",
)
def skills_list(as_json):
    """List newb's skill leaves (SKILL.md + NN_*.md sub-skills).

    \b
    Example:
      $ newb skills list
      $ newb skills list --json
    """
    d = _skills_dir()
    if not d.is_dir():
        raise click.ClickException(f"skills dir missing: {d}")
    leaves = sorted(p.name for p in d.glob("*.md"))
    if as_json:
        click.echo(json.dumps({"skills_dir": str(d), "leaves": leaves}, indent=2))
        return
    click.echo(f"# {d}")
    for name in leaves:
        click.echo(f"  - {name}")


@skills.command("get")
@click.argument("name")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output (path + content fields).",
)
def skills_get(name, as_json):
    """Print one skill leaf's content (e.g. `newb skills get SKILL.md`).

    \b
    Example:
      $ newb skills get SKILL.md
      $ newb skills get 04_isolation
      $ newb skills get 01_quick-start --json
    """
    d = _skills_dir()
    p = d / name
    # also accept partial-name lookup
    if not p.is_file():
        candidates = [c for c in d.glob("*.md") if name in c.name]
        if len(candidates) == 1:
            p = candidates[0]
        elif len(candidates) > 1:
            raise click.ClickException(
                f"ambiguous skill name {name!r}; matches: "
                + ", ".join(c.name for c in candidates)
            )
        else:
            raise click.ClickException(f"unknown skill: {name!r}")
    content = p.read_text(encoding="utf-8")
    if as_json:
        click.echo(json.dumps({"path": str(p), "content": content}, indent=2))
        return
    click.echo(content, nl=False)


# ---------------------------------------------------------------------------
# list-python-apis — required top-level command per scitex audit-cli §1a
# ---------------------------------------------------------------------------


@main.command("list-python-apis")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output.",
)
def list_python_apis(as_json):
    """List newb's public Python API surface (callables in `import newb`).

    \b
    Example:
      $ newb list-python-apis
      $ newb list-python-apis --json
    """
    import inspect

    import newb as _newb

    rows = []
    for name in sorted(getattr(_newb, "__all__", []) or dir(_newb)):
        if name.startswith("_"):
            continue
        obj = getattr(_newb, name, None)
        if obj is None:
            continue
        kind = "callable" if callable(obj) else type(obj).__name__
        try:
            sig = str(inspect.signature(obj)) if callable(obj) else ""
        except (TypeError, ValueError):
            sig = ""
        rows.append({"name": name, "kind": kind, "signature": sig})
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    for r in rows:
        click.echo(f"{r['name']}{r['signature']}  [{r['kind']}]")


# ---------------------------------------------------------------------------
# mcp — server lifecycle + tool listing (parity with scitex-* convention)
# ---------------------------------------------------------------------------


@main.group()
def mcp():
    """MCP server commands (start, list-tools)."""


@mcp.command("list-tools")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output.",
)
def mcp_list_tools(as_json):
    """List MCP tools exposed by newb's server.

    \b
    Example:
      $ newb mcp list-tools
      $ newb mcp list-tools --json
    """
    try:
        from ._server import mcp as _mcp_server
    except ImportError as e:
        raise click.ClickException(
            f"MCP support requires the [mcp] extra: pip install 'newb[mcp]' ({e})"
        ) from e
    # FastMCP exposes tools via _tool_manager._tools (versioned across releases).
    tool_mgr = getattr(_mcp_server, "_tool_manager", None) or getattr(
        _mcp_server, "tool_manager", None
    )
    if tool_mgr and hasattr(tool_mgr, "_tools"):
        tools = list(tool_mgr._tools.values())
    else:
        tools = []
    rows = [
        {
            "name": getattr(t, "name", "?"),
            "description": (getattr(t, "description", "") or "").strip().splitlines()[0]
            if getattr(t, "description", None)
            else "",
        }
        for t in tools
    ]
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    for r in rows:
        click.echo(f"{r['name']}  — {r['description']}")


@mcp.command("start")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the planned action and exit (don't bind / serve).",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Bypass any TTY confirm (no-op here; present for SciTeX CLI parity).",
)
def mcp_start(dry_run, yes):
    """Start the newb MCP server (stdio transport).

    \b
    Example:
      $ newb mcp start
      $ newb mcp start --dry-run
    """
    if dry_run:
        click.echo("would start: newb MCP server on stdio transport (3 tools)")
        return
    _ = yes  # consumed for SciTeX CLI parity
    try:
        from ._server import run_server
    except ImportError as e:
        raise click.ClickException(
            f"MCP support requires the [mcp] extra: pip install 'newb[mcp]' ({e})"
        ) from e
    run_server()


# ---------------------------------------------------------------------------
# Backward-compat shim — `newb <source>` (without `verify`) → `newb verify <source>`
# ---------------------------------------------------------------------------


# Names of registered subcommand groups — keep in sync with the @main.group
# decorators above. Used by _legacy_dispatch to know what NOT to rewrite.
_SUBCOMMANDS = {"verify", "templates", "skills", "mcp", "list-python-apis"}


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
    # If first arg is a known subcommand or starts with a flag, no rewrite.
    if first in _SUBCOMMANDS or first.startswith("-"):
        return
    sys.argv = [sys.argv[0], "verify"] + argv


if __name__ == "__main__":
    _legacy_dispatch()
    main()
else:
    # Also rewrite when invoked through the entry-point script.
    _legacy_dispatch()
