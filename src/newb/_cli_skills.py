"""CLI: ``newb skills list/get`` — introspect newb's own skill leaves.

Reads from ``src/newb/_skills/newb/`` (the skill files newb ships
about itself). Attached to the top-level ``main`` group via
``main.add_command(skills)`` in ``_cli.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import click


@click.group()
def skills():
    """newb's own agent-facing skill leaves (under src/newb/_skills/newb/)."""


def _skills_dir() -> Path:
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
