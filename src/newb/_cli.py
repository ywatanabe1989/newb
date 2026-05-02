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
    # Single-pass scan respecting "next arg is a value" for known
    # value-taking flags. Treat unknown ``--name VAL`` as flag+value.
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
            # If this option takes a value as the next token, consume it.
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
                # Only swallow if the next token is NOT itself a likely positional.
                # (We don't actually know SOURCE shape, but options registered above
                # all take exactly one value, so this is safe in practice.)
                if a in value_taking:
                    out_options.append(argv[i + 1])
                    i += 2
                    continue
            i += 1
            continue
        # First non-option positional.
        if a in _SUBCOMMANDS:
            return argv  # subcommand invocation — leave alone
        positional = a
        i += 1
    if positional is None:
        return argv
    return out_options + rest_after + [positional]


from ._try import render_markdown
from ._try import test as _run_impl
from .question_templates import DEFAULT_TEMPLATE, TEMPLATES


def _print_help_recursive(ctx: click.Context, _param, value):
    """Flatten help for the top command + every subcommand."""
    if not value or ctx.resilient_parsing:
        return
    cmd = ctx.command
    click.echo(cmd.get_help(ctx))
    if isinstance(cmd, click.Group):
        for name in sorted(cmd.commands):
            sub = cmd.commands[name]
            sub_ctx = click.Context(sub, info_name=name, parent=ctx)
            click.echo("\n---\n")
            click.echo(sub.get_help(sub_ctx))
    ctx.exit(0)


def _print_top_level_json(ctx: click.Context, _param, value):
    """Top-level --json (no positional, no subcommand): emit a JSON
    summary of registered subcommands. When SOURCE is positional,
    --json acts as a `--format json` alias inside the try action."""
    if not value or ctx.resilient_parsing:
        return
    # Only handle the introspection mode here; the try-action's --json
    # is consumed downstream.
    if ctx.params.get("source"):
        return
    cmd = ctx.command
    rows = []
    if isinstance(cmd, click.Group):
        for name in sorted(cmd.commands):
            sub = cmd.commands[name]
            rows.append(
                {
                    "name": name,
                    "kind": "group" if isinstance(sub, click.Group) else "command",
                    "summary": (sub.help or "").strip().splitlines()[0]
                    if sub.help
                    else "",
                }
            )
    click.echo(json.dumps({"prog": "newb", "subcommands": rows}, indent=2))
    ctx.exit(0)


# ---------------------------------------------------------------------------
# Top-level group — also runs the "try" action when invoked with a positional
# ---------------------------------------------------------------------------


class _NewbGroup(click.Group):
    """Group that yields to subcommand resolution before consuming the
    optional SOURCE positional. Without this, ``newb templates list``
    is parsed as ``newb SOURCE=templates`` and ``list`` falls off the
    end as an unknown subcommand."""

    def parse_args(self, ctx, args):
        first_pos = next((a for a in args if not a.startswith("-")), None)
        if first_pos and first_pos in self.commands:
            saved = list(self.params)
            self.params = [
                p
                for p in saved
                if not (isinstance(p, click.Argument) and p.name == "source")
            ]
            try:
                result = super().parse_args(ctx, args)
            finally:
                self.params = saved
            ctx.params.setdefault("source", None)
            return result
        return super().parse_args(ctx, args)


@click.group(
    cls=_NewbGroup,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.argument("source", required=False)
@click.option("--model", default="claude-haiku-4-5", help="Claude model id.")
@click.option("--runs", default=1, type=int, help="Runs per prompt.")
@click.option(
    "--template",
    type=click.Choice(sorted(TEMPLATES)),
    default=DEFAULT_TEMPLATE,
    help="Question template — which prompt set to send the agent.",
)
@click.option(
    "--format",
    "out_format",
    type=click.Choice(["json", "markdown"]),
    default="json",
    help="Output format.",
)
@click.option(
    "--json",
    "json_alias",
    is_flag=True,
    default=False,
    help="Alias for --format json (universal SciTeX flag).",
)
@click.option(
    "--markdown",
    "md_alias",
    is_flag=True,
    default=False,
    help="Alias for --format markdown.",
)
@click.option(
    "--runtime",
    type=click.Choice(["docker", "podman", "apptainer"]),
    default="docker",
    help="Container runtime. docker (default), podman (rootless), or apptainer (HPC).",
)
@click.option(
    "--scope",
    type=click.Choice(["all", "docs"]),
    default="all",
    help=(
        "Agent scope. 'all' (default): full agentic permissions — agent "
        "can install/run/test the package. 'docs': read-only audit mode "
        "— Read/Glob/Grep only, no Bash/Write/Edit."
    ),
)
@click.option(
    "--install-mode",
    type=click.Choice(["editable", "wheel", "pypi"]),
    default="editable",
    help=(
        "How the agent installs the package for post_install_check. "
        "'editable' (default): pip install -e . (dev loop). "
        "'wheel': build a wheel and install it (release sanity). "
        "'pypi': pip install <pkg-name> from PyPI (real-user reproduction)."
    ),
)
@click.option(
    "--harden-memory",
    default=None,
    metavar="SIZE",
    help="Container memory cap, e.g. 2g. Default: unlimited (agent runs free).",
)
@click.option(
    "--harden-cpus",
    default=None,
    metavar="N",
    help="Container CPU cap (cores). Default: unlimited.",
)
@click.option(
    "--harden-pids-limit",
    default=None,
    type=int,
    metavar="N",
    help="Container PID cap. Default: unlimited.",
)
@click.option(
    "--harden-no-network/--harden-network",
    default=None,
    help="--harden-no-network adds --network=none (breaks pip + SDK; only for fully offline workflows). Default: bridge.",
)
@click.option(
    "--harden-tmpfs-noexec/--no-harden-tmpfs-noexec",
    default=None,
    help="Mount /tmp with noexec,nosuid. Default: off (pip/pytest sometimes write+exec wheels in /tmp).",
)
@click.option(
    "--pip-cache",
    "pip_cache",
    default=None,
    metavar="PATH",
    help=(
        "Mount a host pip cache into the container at "
        "~/.cache/pip. Speeds up local-dev iteration on repeated "
        "runs. Leave unset for CI (cold install is the honest "
        "newbie test). Falls back to NEWB_PIP_CACHE_DIR."
    ),
)
@click.option(
    "--help-recursive",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_help_recursive,
    help="Flatten help for every subcommand.",
)
@click.version_option(prog_name="newb")
@click.pass_context
def main(
    ctx: click.Context,
    source,
    model,
    runs,
    template,
    out_format,
    json_alias,
    md_alias,
    runtime,
    scope,
    install_mode,
    harden_memory,
    harden_cpus,
    harden_pids_limit,
    harden_no_network,
    harden_tmpfs_noexec,
    pip_cache,
):
    """A fresh AI agent tries to use your package — pytest-style.

    \b
    Example:
        $ newb .                                # current project
        $ newb https://github.com/user/repo.git # git URL — shallow-clones
        $ newb . --template cli-tool --json
        $ newb templates list                   # introspect
        $ newb mcp start                        # MCP server (stdio)

    SOURCE may be a local directory or a git URL (https://, git@, *.git).
    A sandboxed container session reads your project (respecting
    .gitignore) and answers the questions in the chosen template.
    Runtime defaults to docker; auth via NEWB_ANTHROPIC_API_KEY.
    """
    if ctx.invoked_subcommand is not None:
        return  # subcommand handler will run
    if source is None:
        click.echo(ctx.get_help())
        ctx.exit(0)
    # Friendly deprecation hint for the old verb-prefixed forms — the
    # 0.9.x line had `newb verify <SOURCE>` and `newb verify-package
    # <SOURCE>`. Pytest-style dropped both. Direct users to the new form.
    if source in {"verify", "verify-package", "try", "test"}:
        click.echo(
            f"\u26a0\ufe0f  `newb {source} ...` was removed in 0.10.0 — "
            "the canonical invocation is now pytest-style: `newb <target>`. "
            "(Drop the `verify` / `verify-package` token; everything else "
            "stays the same.)",
            err=True,
        )
        ctx.exit(2)
    if json_alias:
        out_format = "json"
    if md_alias:
        out_format = "markdown"

    # [tool.newb] in pyproject.toml: project-level defaults. CLI flags
    # win when explicitly passed; otherwise pyproject value applies.
    # Click defaults are themselves "explicit" from Click's POV, so the
    # only way to know "user didn't pass" is to compare against the
    # default. For now, layer pyproject UNDER hard-coded defaults: the
    # user-passed CLI value (which equals the default if not passed) is
    # preserved, and pyproject acts as a doc-only override channel for
    # template / runtime / scope when the user-passed value matches the
    # built-in default.
    from ._pyproject_config import load_pyproject_config

    project_cfg = load_pyproject_config(source if source else ".")
    if template == "python-package" and project_cfg.get("template"):
        template = project_cfg["template"]
    if runtime == "docker" and project_cfg.get("runtime"):
        runtime = project_cfg["runtime"]
    if scope == "all" and project_cfg.get("scope"):
        scope = project_cfg["scope"]
    if model == "claude-haiku-4-5" and project_cfg.get("model"):
        model = project_cfg["model"]
    if runs == 1 and project_cfg.get("runs"):
        runs = int(project_cfg["runs"])
    if install_mode == "editable" and project_cfg.get("install_mode"):
        install_mode = project_cfg["install_mode"]
    mcp_servers_cfg: dict | None = project_cfg.get("mcp_servers") or None
    if mcp_servers_cfg:
        from ._mcp_inject import McpInjectError, validate as _mcp_validate

        try:
            mcp_servers_cfg = _mcp_validate(mcp_servers_cfg)
        except McpInjectError as e:
            click.echo(f"\u26a0\ufe0f  [tool.newb] mcp_servers: {e}", err=True)
            ctx.exit(2)

    # Resolve hardening: env vars first (NEWB_HARDEN_*), then CLI flags
    # override (None = absent flag, leaves env-supplied value untouched).
    from ._hardening import HardeningOptions

    hardening = HardeningOptions.from_env().merged_with(
        memory=harden_memory,
        cpus=harden_cpus,
        pids_limit=harden_pids_limit,
        no_network=harden_no_network,
        tmpfs_noexec=harden_tmpfs_noexec,
    )

    click.echo(f"\U0001f41d newb: trying {source} ...", err=True)
    result = _run_impl(
        source,
        model=model,
        runs_per_prompt=runs,
        runtime=runtime,
        template=template,
        hardening=hardening,
        scope=scope,
        install_mode=install_mode,
        mcp_servers=mcp_servers_cfg,
        pip_cache_dir=pip_cache,
    )
    if out_format == "markdown":
        click.echo(render_markdown(result), nl=False)
    else:
        click.echo(json.dumps(result, indent=2))
    summary = result.get("tests_summary")
    if summary:
        p, t = summary["passed"], summary["total"]
        emoji = (
            "\U0001f41d\u2705"
            if p == t
            else ("\U0001f41d\u26a0\ufe0f" if p > 0 else "\U0001f41d\u274c")
        )
        click.echo(f"{emoji} {p}/{t} tests passed", err=True)
    else:
        click.echo(
            "\U0001f41d smoke check complete (no tests_newb.yaml found)", err=True
        )


# ---------------------------------------------------------------------------
# Subcommand groups (extracted into sibling modules for line-budget hygiene)
# ---------------------------------------------------------------------------


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
