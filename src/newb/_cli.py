"""newb CLI — ``newb verify <skills_dir>``."""

from __future__ import annotations

import json

import click

from ._verify import render_markdown, verify as _verify_impl


@click.group()
@click.version_option()
def main():
    """newb — agentic testing for Python packages."""


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
def verify(skills_dir, model, runs, out_format, as_json):
    """Verify your package is usable by a fresh AI agent.

    \b
    Example:
        $ newb verify ./src/mypkg/_skills/mypkg
        $ newb verify ./_skills --format markdown >> README.md
    """
    result = _verify_impl(skills_dir, model=model, runs_per_prompt=runs)
    effective = "json" if as_json else out_format
    if effective == "markdown":
        click.echo(render_markdown(result), nl=False)
    else:
        click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
