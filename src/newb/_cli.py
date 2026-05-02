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

# Subcommand names registered on the top-level group. Used by
# _reorder_argv to tell "subcommand invocation" from "implicit-try
# invocation with options after the SOURCE positional".
_SUBCOMMANDS = {"templates", "skills", "mcp", "list-python-apis", "env-template"}


def cli_entrypoint():
    """Console-script entry — preprocess argv (so ``newb <SOURCE>
    [options...]`` works), then hand off to Click."""
    # Load NEWB_ENV_SRC early so all CLI flag resolution + downstream
    # reads of NEWB_* vars see the unified shell-profile config.
    # SciTeX standard env-loader pattern.
    from ._env_loader import load_newb_env

    load_newb_env()
    sys.argv[1:] = _reorder_argv(sys.argv[1:])
    return main()


def _reorder_argv(argv: list[str]) -> list[str]:
    """Allow ``newb <SOURCE> [options...]`` ordering, not just the
    Click-default ``newb [options...] <SOURCE>``.

    Click's ``invoke_without_command=True`` group treats anything after
    the SOURCE positional as a subcommand name, so ``newb /path
    --format markdown`` parses ``--format`` as a subcommand and
    explodes. We pre-walk argv: if a non-subcommand positional appears,
    rotate it to the end so all options precede it from Click's POV.

    Untouched cases (returned verbatim):
      * No positional at all.
      * First positional IS a registered subcommand (let Click route).
      * The argv contains ``--`` (caller asked for explicit separation).
    """
    if not argv or "--" in argv:
        return argv
    value_taking = {
        "--model",
        "--runs",
        "--template",
        "--format",
        "--runtime",
    }
    out_options: list[str] = []
    positional: str | None = None
    rest_after: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if positional is not None:
            rest_after.append(a)
            i += 1
            continue
        if a.startswith("-"):
            out_options.append(a)
            takes_value = (a in value_taking) or (
                a.startswith("--")
                and "=" not in a
                and a
                not in {
                    "--json",
                    "--help-recursive",
                    "--help",
                    "-h",
                    "--version",
                }
            )
            if takes_value and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                if a in value_taking:
                    out_options.append(argv[i + 1])
                    i += 2
                    continue
            i += 1
            continue
        if a in _SUBCOMMANDS:
            return argv  # subcommand invocation — leave alone
        positional = a
        i += 1
    if positional is None:
        return argv
    return out_options + rest_after + [positional]


# ---------------------------------------------------------------------------
# Top-level group + implicit-try action live in ``_cli_try``.
# Subcommands attach here.
# ---------------------------------------------------------------------------

from ._cli_try import main  # noqa: E402

from ._cli_env import env_template as _env_template_cmd  # noqa: E402
from ._cli_mcp import mcp as _mcp_group  # noqa: E402
from ._cli_skills import skills as _skills_group  # noqa: E402
from ._cli_templates import templates as _templates_group  # noqa: E402

main.add_command(_templates_group)
main.add_command(_skills_group)
main.add_command(_mcp_group)
main.add_command(_env_template_cmd)


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
