"""TRUE end-to-end tests — actually exec docker against the published image.

These tests catch regressions that the mock-subprocess unit tests
in ``tests/newb/test__container_runner.py`` can't (e.g. host expects
``/work/project`` but the cached image still has ``/work/skills``).

Auto-skip when:

- ``docker`` isn't on PATH
- ``NEWB_ANTHROPIC_API_KEY`` (the single opt-in flag) isn't set
- explicitly opted-out via ``NEWB_SKIP_E2E=1``

Triggered manually with ``pytest tests/e2e/`` or by setting
``NEWB_RUN_E2E=1`` in CI for nightly runs (the daily Test workflow
keeps using the fast unit tests).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_HAS_DOCKER = shutil.which("docker") is not None
_HAS_KEY = bool(os.environ.get("NEWB_ANTHROPIC_API_KEY"))
_HAS_CREDS = (Path.home() / ".claude" / ".credentials.json").is_file()
_OPT_OUT = os.environ.get("NEWB_SKIP_E2E") == "1"

requires_docker_and_key = pytest.mark.skipif(
    _OPT_OUT or not (_HAS_DOCKER and _HAS_KEY and _HAS_CREDS),
    reason=(
        "e2e: needs docker on PATH, NEWB_ANTHROPIC_API_KEY set, AND "
        "~/.claude/.credentials.json present; skip via NEWB_SKIP_E2E=1"
    ),
)


@pytest.fixture
def newb_repo() -> Path:
    """The repo root we're testing IN — newb itself."""
    here = Path(__file__).resolve()
    return here.parents[2]


def _newb_cli() -> str:
    """Locate the installed `newb` console script (matches sys.executable)."""
    import sys

    p = Path(sys.executable).parent / "newb"
    if not p.is_file():
        raise FileNotFoundError(
            f"newb console script not at {p} — is newb installed in this env?"
        )
    return str(p)


@pytest.fixture
def _newb_against_self_proc(newb_repo: Path) -> subprocess.CompletedProcess[str]:
    """Run ``newb <newb-repo>`` once and share the result across e2e tests
    that need to inspect different aspects of it (rc, JSON, stderr).
    """
    return subprocess.run(
        # Click @group with own options + subcommands consumes its
        # options BEFORE the positional. Put flags first.
        [_newb_cli(), "--runs", "1", "--format", "json", str(newb_repo)],
        capture_output=True,
        text=True,
        timeout=600,
    )


@requires_docker_and_key
def test_docker_runner_against_newb_self_exits_zero(_newb_against_self_proc):
    """`newb <newb-repo>` end-to-end exits 0 (real docker, real Claude)."""
    # Arrange
    proc = _newb_against_self_proc
    # Act
    rc = proc.returncode
    # Assert
    assert rc == 0, (
        f"newb exited rc={rc}\n--- STDOUT ---\n{proc.stdout[:1500]}"
        f"\n--- STDERR ---\n{proc.stderr[:1500]}"
    )


@requires_docker_and_key
def test_docker_runner_against_newb_self_report_has_canonical_keys(
    _newb_against_self_proc, newb_repo: Path
):
    """E2E report has the python-package canonical key set and non-empty values."""
    # Arrange
    expected_keys = (
        "what_for",
        "problems_solved",
        "quick_start",
        "when_not_to_use",
        "post_install_check",
        "prompt_injection_check",
    )
    proc = _newb_against_self_proc
    # Act
    report = json.loads(proc.stdout)
    missing_or_empty = [
        k
        for k in expected_keys
        if k not in report
        or not isinstance(report[k], str)
        or not report[k].strip()
    ]
    # Assert
    assert (
        not missing_or_empty
        and report.get("package") == newb_repo.name
        and report.get("template") == "python-package"
    ), (missing_or_empty, report.get("package"), report.get("template"))


@requires_docker_and_key
def test_docker_image_path_matches_host_mount(newb_repo: Path):
    """Negative regression test for the v0.10.0 break:

    if the image on disk has ``cwd=/work/skills`` (old) but the host
    container_runner mounts ``/work/project`` (new), the SDK reports
    ``CLIConnectionError: Working directory does not exist``. Detect
    that string in stderr if it appears.
    """
    # Arrange
    # Act
    proc = subprocess.run(
        # Click @group with own options + subcommands consumes its
        # options BEFORE the positional. Put flags first.
        [_newb_cli(), "--runs", "1", "--format", "json", str(newb_repo)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    combined = (proc.stdout + proc.stderr).lower()
    # Assert
    assert "working directory does not exist" not in combined, (
        "host/container path mismatch — likely a stale local image. "
        "Run `docker pull ghcr.io/ywatanabe1989/newb-runner:<this-newb-version>` "
        "and retry."
    )
