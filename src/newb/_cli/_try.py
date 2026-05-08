"""``newb <source>`` — the implicit-try action.

Extracted from ``_cli.py`` for line-budget hygiene. Exposes:

- ``main`` — the top-level Click group (subcommands attach to it from
  ``_cli.py`` via ``main.add_command(...)``).
- ``_NewbGroup`` — group subclass that yields to subcommand resolution
  before consuming the optional SOURCE positional. Without this,
  ``newb templates list`` is parsed as ``newb SOURCE=templates`` and
  ``list`` falls off the end as an unknown subcommand.

The decorator stack on ``main`` carries every flag the implicit-try
action needs (model, template, runtime, scope, install-mode, harden-*,
pip-cache, verbosity). The body resolves CLI > ``[tool.newb]`` >
defaults, calls ``newb._try.run``, and prints the report.
"""

from __future__ import annotations

import json
import time

import click

from .._try import render_markdown
from .._try import run as _run_impl
from ..question_templates import DEFAULT_TEMPLATE, TEMPLATES


def _find_subcommand_path(
    group: click.Group, name: str, prefix: tuple[str, ...] = ()
) -> tuple[str, ...] | None:
    """Search ``group`` recursively for a subcommand named ``name``.

    Returns the path of subcommand names from the root group to the
    matching leaf (e.g. ``("dev", "rotate-github-secrets")``), or
    ``None`` if no match is found.
    """
    for sub_name, sub_cmd in group.commands.items():
        if sub_name == name:
            return prefix + (sub_name,)
        if isinstance(sub_cmd, click.Group):
            hit = _find_subcommand_path(sub_cmd, name, prefix + (sub_name,))
            if hit is not None:
                return hit
    return None


def _looks_like_subcommand_typo(source: str) -> bool:
    """True iff ``source`` looks like a CLI verb the user mistyped at top
    level — no path separator, no dot, no URL scheme. We only suggest a
    correction when the spelling fits a verb shape (avoids false positives
    on legitimate bare-name directories like ``newb mypkg``)."""
    return (
        "/" not in source
        and "\\" not in source
        and ":" not in source
        and not source.startswith(".")
        and "." not in source
    )


def _newb_version() -> str:
    """Resolve the installed newb version, or '?' on lookup failure."""
    try:
        from importlib.metadata import version

        return version("newb")
    except Exception:
        return "?"


class _NewbGroup(click.Group):
    """Yield to subcommand resolution before consuming the optional
    SOURCE positional, and prepend ``newb (vX.Y.Z) — <desc>`` to help
    output (per the SciTeX CLI audit §4 canonical-opening-line rule)."""

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

    def format_help_text(self, ctx, formatter):
        # Canonical opening line: `<cli> (vX.Y.Z) — <description>`.
        # Use the runtime-resolved version so the literal can never
        # drift from pyproject.toml.
        first_doc_line = (self.help or "").strip().splitlines()[0:1]
        desc = first_doc_line[0] if first_doc_line else ""
        formatter.write_paragraph()
        formatter.write_text(f"newb (v{_newb_version()}) — {desc}")
        super().format_help_text(ctx, formatter)


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


@click.group(
    cls=_NewbGroup,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=(
        f"newb (v{_newb_version()}) — A fresh AI agent tries to use your "
        "package — pytest-style. Run `newb <SOURCE>` against any project "
        "directory or git URL."
    ),
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
        "Agent scope. 'all' (default): full agentic permissions — "
        "agent can install/run/test the package. 'docs': read-only "
        "audit mode — Read/Glob/Grep only, no Bash/Write/Edit."
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
    help=(
        "--harden-no-network adds --network=none (breaks pip + SDK; "
        "only for fully offline workflows). Default: bridge."
    ),
)
@click.option(
    "--harden-tmpfs-noexec/--no-harden-tmpfs-noexec",
    default=None,
    help=(
        "Mount /tmp with noexec,nosuid. Default: off (pip/pytest "
        "sometimes write+exec wheels in /tmp)."
    ),
)
@click.option(
    "--pip-cache",
    "pip_cache",
    default=None,
    metavar="PATH",
    help=(
        "Mount a host pip cache into the container at ~/.cache/pip. "
        "Speeds up local-dev iteration on repeated runs. Leave unset "
        "for CI (cold install is the honest newbie test). Falls back "
        "to NEWB_PIP_CACHE_DIR."
    ),
)
@click.option(
    "-v",
    "--verbose",
    "verbosity",
    count=True,
    help=(
        "Verbosity: -v echoes the resolved config + total wall time; "
        "-vv also streams container stderr in real time (per-prompt "
        "timing + SDK chatter); -vvv adds the raw container argv."
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
@click.version_option(None, "-V", "--version", prog_name="newb")
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
    verbosity,
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
    # <SOURCE>`. Pytest-style dropped both.
    if source in {"verify", "verify-package", "try", "test"}:
        click.echo(
            f"\u26a0\ufe0f  `newb {source} ...` was removed in 0.10.0 — "
            "the canonical invocation is now pytest-style: `newb <target>`. "
            "(Drop the `verify` / `verify-package` token; everything else "
            "stays the same.)",
            err=True,
        )
        ctx.exit(2)
    # If SOURCE looks like a verb (no path / URL shape) and doesn't exist
    # locally, check whether it's a subcommand the user forgot to prefix
    # (e.g. `newb rotate-github-secrets` instead of `newb dev rotate-…`).
    # We do this BEFORE _validate_source's FileNotFoundError so the user
    # gets actionable guidance instead of a confusing path error.
    from pathlib import Path as _Path

    if _looks_like_subcommand_typo(source) and not _Path(source).exists():
        root = ctx.command if isinstance(ctx.command, click.Group) else main
        match = _find_subcommand_path(root, source)
        if match is not None:
            click.echo(
                f"newb: '{source}' is not a top-level command. Did you mean "
                f"`newb {' '.join(match)}`?",
                err=True,
            )
            ctx.exit(2)
        click.echo(
            f"newb: '{source}' is neither a path nor a known subcommand. "
            "Run `newb --help` for the command list.",
            err=True,
        )
        ctx.exit(2)
    if json_alias:
        out_format = "json"
    if md_alias:
        out_format = "markdown"

    # CLI > [tool.newb] > built-in defaults.
    from .._pyproject_config import load_pyproject_config

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
        from .._mcp._inject import McpInjectError
        from .._mcp._inject import validate as _mcp_validate

        try:
            mcp_servers_cfg = _mcp_validate(mcp_servers_cfg)
        except McpInjectError as e:
            click.echo(f"\u26a0\ufe0f  [tool.newb] mcp_servers: {e}", err=True)
            ctx.exit(2)

    # Resolve hardening: env vars first, CLI flags override.
    from .._hardening import HardeningOptions

    hardening = HardeningOptions.from_env().merged_with(
        memory=harden_memory,
        cpus=harden_cpus,
        pids_limit=harden_pids_limit,
        no_network=harden_no_network,
        tmpfs_noexec=harden_tmpfs_noexec,
    )

    click.echo(f"\U0001f41d newb: trying {source} ...", err=True)
    if verbosity >= 1:
        click.echo(
            "  config: "
            f"model={model} template={template} runtime={runtime} "
            f"scope={scope} install_mode={install_mode} runs={runs}",
            err=True,
        )
        if mcp_servers_cfg:
            click.echo(f"  mcp_servers: {sorted(mcp_servers_cfg)}", err=True)
        if pip_cache:
            click.echo(f"  pip_cache: {pip_cache}", err=True)

    t0 = time.monotonic()
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
        verbosity=verbosity,
    )
    if verbosity >= 1:
        click.echo(f"  wall-clock: {time.monotonic() - t0:.1f}s", err=True)
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
            "\U0001f41d smoke check complete (no tests_newb.yaml found)",
            err=True,
        )


# EOF
