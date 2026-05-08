"""CLI: ``newb show-env-template`` — emit a copy-pasteable .src file.

Standard SciTeX show-env-template pattern: prints (or writes) a template
listing all NEWB_* env vars with descriptions + commented-out examples.
Source the file from your shell profile, or point ``NEWB_ENV_SRC`` at
it so newb auto-loads on startup.
"""

from __future__ import annotations

from pathlib import Path

import click


@click.command("show-env-template")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write to a file instead of stdout.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON (env-var schema) instead of the .src template.",
)
def env_template(output: str | None, as_json: bool):
    """Emit a copy-pasteable NEWB_* env-var template.

    \b
    Example:
      $ newb show-env-template                              # to stdout
      $ newb show-env-template -o ~/.config/newb/local.src  # to file
      $ newb show-env-template --json                       # JSON schema
    """
    import json as _json

    from .._env._registry import REGISTRY, generate_template

    if as_json:
        rows = [
            {"name": e.name, "description": e.description, "default": e.default}
            for e in REGISTRY
        ]
        click.echo(_json.dumps(rows, indent=2))
        return
    content = generate_template()
    if output:
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        click.echo(f"wrote {path}", err=True)
        return
    click.echo(content, nl=False)
