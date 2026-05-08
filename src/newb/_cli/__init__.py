"""newb CLI — pytest-style.

Primary form (no subcommand needed):

    newb <target>                  → a fresh agent tries to use the package

Subcommands are introspection-only:

    newb templates list / show
    newb skills list / get
    newb mcp list-tools / start
    newb list-python-apis

Mental model: a newbie tries something. The CLI's default action is the
"try" — pytest-style positional, no verb in front.

The implicit-try action's giant Click decorator stack lives in
``_cli_try.py`` (line-budget hygiene). This module is now an
orchestrator: argv preprocessing, the entrypoint, and subcommand
registrations onto the ``main`` group imported from ``_cli_try``.
"""

from __future__ import annotations

import json
import sys

import click

from ._reorder import _reorder_argv, _SUBCOMMANDS  # noqa: F401


def cli_entrypoint():
    """Console-script entry — preprocess argv (so ``newb <SOURCE>
    [options...]`` works), then hand off to Click."""
    # Load NEWB_ENV_SRC early so all CLI flag resolution + downstream
    # reads of NEWB_* vars see the unified shell-profile config.
    # SciTeX standard env-loader pattern.
    from .._env._loader import load_newb_env

    load_newb_env()
    sys.argv[1:] = _reorder_argv(sys.argv[1:])
    return main()


# ---------------------------------------------------------------------------
# Top-level group + implicit-try action live in ``_cli_try``.
# Subcommands attach here.
# ---------------------------------------------------------------------------

from ._try import main  # noqa: E402

from ._completion import (  # noqa: E402
    install_shell_completion as _install_shell_completion_cmd,
    print_shell_completion as _print_shell_completion_cmd,
)
from ._dev import dev as _dev_group  # noqa: E402
from ._env import env_template as _env_template_cmd  # noqa: E402
from ._gate import gate as _gate_cmd  # noqa: E402
from ._mcp import mcp as _mcp_group  # noqa: E402
from ._skills import skills as _skills_group  # noqa: E402
from ._templates import templates as _templates_group  # noqa: E402

main.add_command(_templates_group)
main.add_command(_skills_group)
main.add_command(_mcp_group)
main.add_command(_env_template_cmd)
main.add_command(_gate_cmd)
main.add_command(_dev_group)
main.add_command(_install_shell_completion_cmd)
main.add_command(_print_shell_completion_cmd)


# ---------------------------------------------------------------------------
# list-python-apis (small enough to keep in-line)
# ---------------------------------------------------------------------------


@main.command("list-python-apis")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Machine-readable JSON output.",
)
def list_python_apis(as_json):
    """List newb's public Python API surface (callables in `import newb`).

    \b
    Example:
      $ newb list-python-apis
      $ newb list-python-apis --json
    """
    import inspect

    import newb as _newb

    rows = []
    for name in sorted(getattr(_newb, "__all__", []) or dir(_newb)):
        if name.startswith("_"):
            continue
        obj = getattr(_newb, name, None)
        if obj is None:
            continue
        kind = "callable" if callable(obj) else type(obj).__name__
        try:
            sig = str(inspect.signature(obj)) if callable(obj) else ""
        except (TypeError, ValueError):
            sig = ""
        rows.append({"name": name, "kind": kind, "signature": sig})
    if as_json:
        click.echo(json.dumps(rows, indent=2))
        return
    for r in rows:
        click.echo(f"{r['name']}{r['signature']}  [{r['kind']}]")


if __name__ == "__main__":
    main()
