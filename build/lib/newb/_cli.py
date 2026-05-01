"""newb CLI — ``newb run <skills_dir>``.

Pytest-style design: the primary verb is ``run`` (mirrors ``pytest``).
``verify`` is kept as a hidden alias for backward compatibility from
v0.2.0; it will be removed in 1.0.
"""

from __future__ import annotations

import json

import click

from ._verify import render_markdown
from ._verify import run as _run_impl


@click.group()
@click.version_option()
def main():
    """newb — agentic testing for Python packages."""


def _run_inner(skills_dir, model, runs, out_format, as_json):
    result = _run_impl(skills_dir, model=model, runs_per_prompt=runs)
    effective = "json" if as_json else out_format
    if effective == "markdown":
        click.echo(render_markdown(result), nl=False)
    else:
        click.echo(json.dumps(result, indent=2))


@main.command()
@click.argument("skills_dir", type=click.Path(exists=True, file_okay=False))
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
    "--json",
    "as_json",
    is_flag=True,
    help="(deprecated) Equivalent to --format json.",
)
def run(skills_dir, model, runs, out_format, as_json):
    """Run a fresh AI agent against your package's skills.

    \b
    Example:
        $ newb run ./src/mypkg/_skills/mypkg
        $ newb run ./_skills --format markdown >> README.md
    """
    _run_inner(skills_dir, model, runs, out_format, as_json)


@main.command(hidden=True)
@click.argument("skills_dir", type=click.Path(exists=True, file_okay=False))
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
    "--json",
    "as_json",
    is_flag=True,
    help="(deprecated) Equivalent to --format json.",
)
def verify(skills_dir, model, runs, out_format, as_json):
    """(deprecated) Renamed to ``run`` in v0.3.0; removed in 1.0."""
    _run_inner(skills_dir, model, runs, out_format, as_json)


if __name__ == "__main__":
    main()
