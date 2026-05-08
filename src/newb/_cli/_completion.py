"""``newb install-shell-completion`` / ``newb print-shell-completion``.

SciTeX CLI audit §1a requires every CLI to ship these two commands so
``newb <TAB>`` produces sensible completions. We implement them
natively over Click's built-in completion mechanism (env var
``_NEWB_COMPLETE=<shell>_source newb``), so newb gains no scitex-dev
dependency.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import click


_SHELLS = ("bash", "zsh", "fish")


_RC_PATHS = {
    "bash": "~/.bashrc",
    "zsh": "~/.zshrc",
    "fish": "~/.config/fish/completions/newb.fish",
}


def _click_complete_source(shell: str) -> str:
    """Run ``_NEWB_COMPLETE=<shell>_source newb`` and return stdout.

    Click writes the completion script to stdout when this env var is
    set; we capture it here so the command works without the user
    having to remember the env-var name.
    """
    newb_bin = shutil.which("newb") or "newb"
    env = os.environ.copy()
    env["_NEWB_COMPLETE"] = f"{shell}_source"
    proc = subprocess.run(
        [newb_bin],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise click.ClickException(
            f"failed to generate {shell} completion: "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


@click.command("print-shell-completion")
@click.argument("shell", type=click.Choice(_SHELLS), required=False)
def print_shell_completion(shell: str | None):
    """Print the shell-completion script for SHELL to stdout.

    \b
    Example:
      $ newb print-shell-completion bash
      $ newb print-shell-completion zsh > ~/.zsh-newb-completion
      $ newb print-shell-completion          # auto-detect from $SHELL

    SHELL is one of: bash, zsh, fish. Auto-detected when omitted.
    """
    shell = shell or _detect_shell()
    click.echo(_click_complete_source(shell), nl=False)


@click.command("install-shell-completion")
@click.argument("shell", type=click.Choice(_SHELLS), required=False)
@click.option(
    "--rc-path",
    default=None,
    help="Override the rc / completion file (default depends on shell).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be written without modifying any file.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Skip the interactive confirmation prompt.",
)
def install_shell_completion(
    shell: str | None, rc_path: str | None, dry_run: bool, yes: bool
):
    """Install shell completion for SHELL.

    \b
    Example:
      $ newb install-shell-completion bash
      $ newb install-shell-completion          # auto-detect
      $ newb install-shell-completion zsh --dry-run

    Appends an ``eval`` line (bash/zsh) or writes a completion file
    (fish). Idempotent — re-runs are no-ops.
    """
    shell = shell or _detect_shell()
    rc = Path(rc_path or _RC_PATHS[shell]).expanduser()
    if shell in {"bash", "zsh"}:
        line = f'eval "$(_NEWB_COMPLETE={shell}_source newb)"'
        if dry_run:
            click.echo(f"newb: dry-run — would append to {rc}: {line}")
            return
        if not yes:
            click.echo(
                f"refusing to write {rc} without --yes/-y "
                "(or use --dry-run to preview).",
                err=True,
            )
            return
        rc.parent.mkdir(parents=True, exist_ok=True)
        existing = rc.read_text() if rc.is_file() else ""
        if line in existing:
            click.echo(f"newb: {shell} completion already installed in {rc}")
            return
        with rc.open("a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write(f"# Added by `newb install-shell-completion`\n{line}\n")
        click.echo(f"newb: appended {shell} completion to {rc}")
        return
    # fish
    if dry_run:
        click.echo(f"newb: dry-run — would write fish completion to {rc}")
        return
    if not yes:
        click.echo(
            f"refusing to write {rc} without --yes/-y (or use --dry-run to preview).",
            err=True,
        )
        return
    rc.parent.mkdir(parents=True, exist_ok=True)
    rc.write_text(_click_complete_source("fish"))
    click.echo(f"newb: wrote fish completion to {rc}")


def _detect_shell() -> str:
    sh = os.environ.get("SHELL", "").rsplit("/", 1)[-1]
    if sh in _SHELLS:
        return sh
    raise click.ClickException(
        f"could not auto-detect shell from $SHELL={os.environ.get('SHELL', '')!r}; "
        f"pass one of {_SHELLS} explicitly."
    )


# EOF
