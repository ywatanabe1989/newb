"""CLI: ``newb mcp list-tools/start`` — MCP server lifecycle + introspection.

The actual server lives in ``newb._server`` (FastMCP); these subcommands
just bind it. Attached to the top-level ``main`` group via
``main.add_command(mcp)`` in ``_cli.py``.
"""

from __future__ import annotations

import json

import click


@click.group()
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
        from .._server import mcp as _mcp_server
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
        from .._server import run_server
    except ImportError as e:
        raise click.ClickException(
            f"MCP support requires the [mcp] extra: pip install 'newb[mcp]' ({e})"
        ) from e
    run_server()
