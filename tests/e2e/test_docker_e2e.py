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


@requires_docker_and_key
def test_docker_runner_against_newb_self(newb_repo: Path):
    """`newb <newb-repo>` end-to-end: real docker, real SDK, real Claude.

    Asserts the report has the canonical python-package keys.
    """
    proc = subprocess.run(
        # Click @group with own options + subcommands consumes its
        # options BEFORE the positional. Put flags first.
        [_newb_cli(), "--runs", "1", "--format", "json", str(newb_repo)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, (
        f"newb exited rc={proc.returncode}\n--- STDOUT ---\n{proc.stdout[:1500]}"
        f"\n--- STDERR ---\n{proc.stderr[:1500]}"
    )
    report = json.loads(proc.stdout)
    assert report["package"] == newb_repo.name
    assert report["template"] == "python-package"
    for key in (
        "what_for",
        "problems_solved",
        "quick_start",
        "when_not_to_use",
        "post_install_check",
        "prompt_injection_check",
    ):
        assert key in report, f"missing canonical key: {key}"
        assert isinstance(report[key], str) and report[key].strip()


@requires_docker_and_key
def test_docker_image_path_matches_host_mount(newb_repo: Path):
    """Negative regression test for the v0.10.0 break:

    if the image on disk has ``cwd=/work/skills`` (old) but the host
    container_runner mounts ``/work/project`` (new), the SDK reports
    ``CLIConnectionError: Working directory does not exist``. Detect
    that string in stderr if it appears.
    """
    proc = subprocess.run(
        # Click @group with own options + subcommands consumes its
        # options BEFORE the positional. Put flags first.
        [_newb_cli(), "--runs", "1", "--format", "json", str(newb_repo)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    combined = (proc.stdout + proc.stderr).lower()
    assert "working directory does not exist" not in combined, (
        "host/container path mismatch — likely a stale local image. "
        "Run `docker pull ghcr.io/ywatanabe1989/newb-runner:<this-newb-version>` "
        "and retry."
    )
