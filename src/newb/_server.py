#!/usr/bin/env python3
"""MCP server for newb — exposes the verifier as Claude Code tools.

One tool: ``newb_verify`` — runs a fresh agent in a hard-isolated
container against a docs source and returns the structured report.
``newb_templates_list`` and ``newb_templates_show`` round out the
introspection surface (parity with the CLI's ``newb templates`` group).
"""

from __future__ import annotations

import json
from typing import Optional

from fastmcp import FastMCP

from .question_templates import DEFAULT_TEMPLATE, TEMPLATES

mcp = FastMCP(
    name="newb",
    instructions=(
        "Verify a Python package's documentation by running a fresh AI "
        "agent in a hard-isolated container that reads the project "
        "(respecting .gitignore) and answers canonical questions. The "
        "container is the boundary; inside, the agent has full Read+"
        "Write+Edit+Bash+Glob+Grep so it can actually try the package "
        '(pip install -e ., python -c "import pkg", <pkg> --help). '
        "Use templates: python-package (default, 6 questions including "
        "post-install + prompt-injection check), or cli-tool (6 "
        "questions tuned for CLI-first packages)."
    ),
)


def _json(data: dict) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
async def newb_verify(
    source: str,
    template: str = DEFAULT_TEMPLATE,
    runtime: str = "docker",
    model: str = "claude-haiku-4-5",
    runs_per_prompt: int = 1,
) -> str:
    """Run the verifier against a docs source. Returns the structured report.

    Parameters
    ----------
    source
        Local directory or git URL.
    template
        Question template name (e.g. ``python-package``, ``cli-tool``).
    runtime
        Container backend: ``docker`` (default) or ``apptainer``.
    model
        Claude model id passed to the SDK.
    runs_per_prompt
        Repeat each prompt N times for stability measurement.
    """
    from ._verify import run as _run

    report = _run(
        source,
        model=model,
        runs_per_prompt=runs_per_prompt,
        runtime=runtime,
        template=template,
    )
    return _json(report)


@mcp.tool()
async def newb_templates_list() -> str:
    """List the built-in question templates and their question keys."""
    rows = [
        {"name": name, "questions": list(prompts.keys())}
        for name, prompts in sorted(TEMPLATES.items())
    ]
    return _json({"templates": rows, "default": DEFAULT_TEMPLATE})


@mcp.tool()
async def newb_templates_show(name: str) -> str:
    """Show the prompts in a named question template."""
    if name not in TEMPLATES:
        return _json(
            {
                "error": f"unknown template {name!r}",
                "available": sorted(TEMPLATES),
            }
        )
    return _json({"name": name, "prompts": TEMPLATES[name]})


def run_server(transport: Optional[str] = None) -> None:
    """Run the MCP server (defaults to stdio transport)."""
    if transport:
        mcp.run(transport=transport)
    else:
        mcp.run()


if __name__ == "__main__":
    run_server()
