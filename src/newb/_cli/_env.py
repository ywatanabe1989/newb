"""CLI: ``newb env-template`` — emit a copy-pasteable .src file.

Standard SciTeX env-template pattern: prints (or writes) a template
listing all NEWB_* env vars with descriptions + commented-out examples.
Source the file from your shell profile, or point ``NEWB_ENV_SRC`` at
it so newb auto-loads on startup.
"""

from __future__ import annotations

from pathlib import Path

import click


@click.command("env-template")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write to a file instead of stdout.",
)
def env_template(output: str | None):
    """Emit a copy-pasteable NEWB_* env-var template.

    \b
    Example:
      $ newb env-template                                  # to stdout
      $ newb env-template -o ~/.scitex/newb/local.src      # to file
      $ export NEWB_ENV_SRC=~/.scitex/newb/local.src       # then in your shell rc
    """
    from .._env._registry import generate_template

    content = generate_template()
    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        click.echo(f"wrote {path}", err=True)
        return
    click.echo(content, nl=False)
