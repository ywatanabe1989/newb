"""newb CLI — ``newb <skills_dir>``.

Pytest-style: no subcommand. ``newb ./skills`` runs the agent the same
way ``pytest ./tests`` runs the test suite.
"""

from __future__ import annotations

import json

import click

from ._verify import render_markdown
from ._verify import run as _run_impl


@click.command()
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
@click.version_option()
def main(skills_dir, model, runs, out_format):
    """Run a fresh AI agent against your package's skills.

    \b
    Example:
        $ newb ./src/mypkg/_skills/mypkg
        $ newb ./_skills --format markdown >> README.md
    """
    result = _run_impl(skills_dir, model=model, runs_per_prompt=runs)
    if out_format == "markdown":
        click.echo(render_markdown(result), nl=False)
    else:
        click.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
