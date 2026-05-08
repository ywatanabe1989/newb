"""argv pre-processor for the implicit-try CLI form.

Click's ``invoke_without_command=True`` group treats anything after the
SOURCE positional as a subcommand name, so ``newb /path --format
markdown`` parses ``--format`` as a subcommand and explodes.
``_reorder_argv`` rotates a non-subcommand positional to the end of
argv before Click sees it, so options precede it.

Extracted from ``_cli/__init__.py`` so its unit test (which exercises
the rotation logic directly, without spawning the CLI) has a 1:1 src
mirror per PS204/PS205.
"""

from __future__ import annotations


# Subcommand names registered on the top-level group. Used to tell
# "subcommand invocation" from "implicit-try invocation with options
# after the SOURCE positional".
_SUBCOMMANDS = {
    "templates",
    "skills",
    "mcp",
    "list-python-apis",
    "show-env-template",
    "gate",
    "dev",
    "install-shell-completion",
    "print-shell-completion",
}


def _reorder_argv(argv: list[str]) -> list[str]:
    """Allow ``newb <SOURCE> [options...]`` ordering.

    Click's default is ``newb [options...] <SOURCE>``. We pre-walk argv:
    if a non-subcommand positional appears, rotate it to the end so all
    options precede it from Click's POV.

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


# EOF
