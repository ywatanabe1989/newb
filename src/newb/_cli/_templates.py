"""CLI: ``newb templates list/show`` — introspect built-in templates.

Extracted from ``_cli.py`` for line-budget hygiene. Attached to the
top-level ``main`` group via ``main.add_command(templates)`` in
``_cli.py``.
"""

from __future__ import annotations

import json

import click

from ..question_templates import TEMPLATES


@click.group()
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
