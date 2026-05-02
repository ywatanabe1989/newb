"""newb CLI — pytest-style.

Primary form (no subcommand needed):

    newb <target>                  → a fresh agent tries to use the package

Subcommands are introspection-only:

    newb templates list / show
    newb skills list / get
    newb mcp list-tools / start
    newb list-python-apis

Mental model: a newbie tries something. The CLI's default action is the
"try" — pytest-style positional, no verb in front.
"""

from __future__ import annotations

import json

import click

from ._try import render_markdown
from ._try import run as _run_impl
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


def _print_top_level_json(ctx: click.Context, _param, value):
    """Top-level --json (no positional, no subcommand): emit a JSON
    summary of registered subcommands. When SOURCE is positional,
    --json acts as a `--format json` alias inside the try action."""
    if not value or ctx.resilient_parsing:
        return
    # Only handle the introspection mode here; the try-action's --json
    # is consumed downstream.
    if ctx.params.get("source"):
        return
    cmd = ctx.command
    rows = []
    if isinstance(cmd, click.Group):
        for name in sorted(cmd.commands):
            sub = cmd.commands[name]
            rows.append(
                {
                    "name": name,
                    "kind": "group" if isinstance(sub, click.Group) else "command",
                    "summary": (sub.help or "").strip().splitlines()[0]
                    if sub.help
                    else "",
                }
            )
    click.echo(json.dumps({"prog": "newb", "subcommands": rows}, indent=2))
    ctx.exit(0)


# ---------------------------------------------------------------------------
# Top-level group — also runs the "try" action when invoked with a positional
# ---------------------------------------------------------------------------


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("source", required=False)
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
def main(
    ctx: click.Context,
    source,
    model,
    runs,
    template,
    out_format,
    json_alias,
    runtime,
):
    """A fresh AI agent tries to use your package — pytest-style.

    \b
    Example:
        $ newb .                                # current project
        $ newb https://github.com/user/repo.git # git URL — shallow-clones
        $ newb . --template cli-tool --json
        $ newb templates list                   # introspect
        $ newb mcp start                        # MCP server (stdio)

    SOURCE may be a local directory or a git URL (https://, git@, *.git).
    A sandboxed container session reads your project (respecting
    .gitignore) and answers the questions in the chosen template.
    Runtime defaults to docker; auth via NEWB_ANTHROPIC_API_KEY.
    """
    if ctx.invoked_subcommand is not None:
        return  # subcommand handler will run
    if source is None:
        click.echo(ctx.get_help())
        ctx.exit(0)
    # Friendly deprecation hint for the old verb-prefixed forms — the
    # 0.9.x line had `newb verify <SOURCE>` and `newb verify-package
    # <SOURCE>`. Pytest-style dropped both. Direct users to the new form.
    if source in {"verify", "verify-package", "try", "test"}:
        click.echo(
            f"\u26a0\ufe0f  `newb {source} ...` was removed in 0.10.0 — "
            "the canonical invocation is now pytest-style: `newb <target>`. "
            "(Drop the `verify` / `verify-package` token; everything else "
            "stays the same.)",
            err=True,
        )
        ctx.exit(2)
    if json_alias:
        out_format = "json"
    click.echo(f"\U0001f41d newb: trying {source} ...", err=True)
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
# skills — list / get newb's own _skills/<pkg>/ tree
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
# list-python-apis
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
# mcp — server lifecycle + tool listing
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
    tool_mgr = getattr(_mcp_server, "_tool_manager", None) or getattr(
        _mcp_server, "tool_manager", None
    )
    tools = (
        list(tool_mgr._tools.values())
        if tool_mgr and hasattr(tool_mgr, "_tools")
        else []
    )
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
        click.echo("would start: newb MCP server on stdio transport")
        return
    _ = yes
    try:
        from ._server import run_server
    except ImportError as e:
        raise click.ClickException(
            f"MCP support requires the [mcp] extra: pip install 'newb[mcp]' ({e})"
        ) from e
    run_server()


if __name__ == "__main__":
    main()
