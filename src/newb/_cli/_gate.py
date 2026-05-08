"""``newb gate`` — evaluate a report against pyproject [tool.newb.gate].

Reads a JSON report (produced by ``newb <target> --format json``) from
a path or stdin, applies the gate criteria, prints a one-line PASS/FAIL
summary plus any failures, and exits 0 (pass) or 1 (fail).

Use in CI after the run step, e.g.::

    newb scitex-io --format json > report.json
    newb gate report.json

Or via stdin::

    newb scitex-io --format json | newb gate -
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .._gate import evaluate, load_gate_config


@click.command("gate")
@click.argument("report_path", type=click.Path(dir_okay=False))
@click.option(
    "--pyproject",
    "pyproject_dir",
    type=click.Path(file_okay=False, exists=True),
    default=".",
    show_default=True,
    help="Directory to search upward from for pyproject.toml.",
)
def gate(report_path: str, pyproject_dir: str):
    """Evaluate a newb JSON report against [tool.newb.gate] criteria.

    \b
    Example:
      $ newb . --format json > report.json
      $ newb gate report.json                 # exits 0 (pass) or 1 (fail)
      $ newb . --format json | newb gate -    # via stdin

    Pass '-' as REPORT_PATH to read from stdin.
    """
    if report_path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(report_path).read_text()
    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        click.echo(f"newb gate: not valid JSON: {exc}", err=True)
        sys.exit(2)
    if not isinstance(report, dict):
        click.echo("newb gate: report must be a JSON object", err=True)
        sys.exit(2)
    cfg = load_gate_config(pyproject_dir)
    passed, failures = evaluate(report, cfg)
    if passed:
        click.echo(f"newb gate: PASS ({len(cfg)} criteria checked)")
        sys.exit(0)
    click.echo(f"newb gate: FAIL ({len(failures)} criteria failed)", err=True)
    for f in failures:
        click.echo(f"  - {f}", err=True)
    sys.exit(1)


# EOF
