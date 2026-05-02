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
    from ._try import run as _run

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


def _newb_skills_dir():
    from pathlib import Path

    import newb as _newb

    return Path(_newb.__file__).parent / "_skills" / "newb"


@mcp.tool()
async def newb_skills_list() -> str:
    """List newb's own agent-facing skill leaves."""
    d = _newb_skills_dir()
    if not d.is_dir():
        return _json({"error": f"skills dir missing: {d}"})
    leaves = sorted(p.name for p in d.glob("*.md"))
    return _json({"skills_dir": str(d), "leaves": leaves})


@mcp.tool()
async def newb_skills_get(name: str) -> str:
    """Print one skill leaf's content (partial-name match supported)."""
    d = _newb_skills_dir()
    p = d / name
    if not p.is_file():
        candidates = [c for c in d.glob("*.md") if name in c.name]
        if len(candidates) == 1:
            p = candidates[0]
        elif len(candidates) > 1:
            return _json(
                {
                    "error": f"ambiguous {name!r}",
                    "matches": [c.name for c in candidates],
                }
            )
        else:
            return _json({"error": f"unknown skill: {name!r}"})
    return _json({"path": str(p), "content": p.read_text(encoding="utf-8")})


@mcp.tool()
async def newb_render_markdown(report: dict) -> str:
    """Render a `newb_verify` report dict as a README-ready markdown block."""
    from ._try import render_markdown

    return render_markdown(report)


# Public Python API parity (audit-mcp-tools §6) — `newb.run` /
# mirrors of the Python API exposed as MCP tools so a
# tool-using agent has the same vocabulary as the import-using one.
# Both delegate to newb_verify.


@mcp.tool()
async def newb_run(
    source: str,
    template: str = DEFAULT_TEMPLATE,
    runtime: str = "docker",
    model: str = "claude-haiku-4-5",
    runs_per_prompt: int = 1,
) -> str:
    """Alias for ``newb_verify`` — mirrors the ``newb.run`` Python API."""
    return await newb_verify(  # type: ignore[func-returns-value]
        source=source,
        template=template,
        runtime=runtime,
        model=model,
        runs_per_prompt=runs_per_prompt,
    )


def run_server(transport: Optional[str] = None) -> None:
    """Run the MCP server (defaults to stdio transport)."""
    if transport:
        mcp.run(transport=transport)
    else:
        mcp.run()


if __name__ == "__main__":
    run_server()
