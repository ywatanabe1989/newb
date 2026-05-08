"""``newb dev`` — maintainer plumbing.

A noun group whose verbs are NOT for the package's end-users, but
for whoever maintains the package and operates its CI integration.

Verbs:

* ``install``           — install newb CI into a target repo
* ``set-secret``        — set ``NEWB_ANTHROPIC_API_KEY`` on a repo
* ``scaffold-workflow`` — drop ``.github/workflows/newb.yml``

Auth flow is **strictly one-directional**:

    ``~/.claude/.credentials.json`` → ``NEWB_ANTHROPIC_API_KEY`` →
    ``ANTHROPIC_API_KEY``

The shell bridge in ``01_newb.src`` extracts the access token from
``credentials.json`` (read-only — ``claude /login`` produces it; we
never write it) and exports it as ``NEWB_ANTHROPIC_API_KEY`` at
session startup. ``newb dev set-secret`` then pushes that env value
to a repo's GitHub Actions secret. No middle verb required.

The verbs themselves live in ``_cli_install``; we re-register them
here so users type ``newb dev <verb>`` and we avoid top-level
collisions with SOURCE positionals.
"""

from __future__ import annotations

import click

from ._install import (
    install as _install_cmd,
    scaffold_workflow as _scaffold_cmd,
    set_secret as _set_secret_cmd,
)


@click.group(
    "dev",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def dev():
    """Developer / maintainer plumbing (CI secrets, repo bootstrap)."""


dev.add_command(_install_cmd)
dev.add_command(_set_secret_cmd)
dev.add_command(_scaffold_cmd)


# EOF
