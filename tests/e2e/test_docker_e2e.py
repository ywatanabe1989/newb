"""TRUE end-to-end tests — actually exec docker against the published image.

These tests catch regressions that the argv-shape unit tests in
``tests/newb/test__container_runner.py`` can't (e.g. host expects
``/work/project`` but the cached image still has ``/work/skills``).

Auto-skip when:

- ``docker`` isn't on PATH
- ``NEWB_ANTHROPIC_API_KEY`` (the single opt-in flag) isn't set
- ``~/.claude/.credentials.json`` is absent
- explicitly opted-out via ``NEWB_SKIP_E2E=1``

Triggered manually with ``pytest tests/e2e/`` or by setting the env so
the guard passes.  Marked ``e2e`` (see pyproject markers).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

_HAS_DOCKER = shutil.which("docker") is not None
_HAS_KEY = bool(os.environ.get("NEWB_ANTHROPIC_API_KEY"))
_HAS_CREDS = (Path.home() / ".claude" / ".credentials.json").is_file()
_OPT_OUT = os.environ.get("NEWB_SKIP_E2E") == "1"


def _runner_image_available() -> bool:
    """True iff the version-pinned newb-runner image is pullable.

    Running an e2e against a non-published image is an environment
    problem (a release cut before the image-publish workflow ran), not
    a code regression — so we skip rather than fail with a cryptic
    empty-stdout JSON error. Honours ``NEWB_DOCKER_IMAGE`` override.
    """
    if not _HAS_DOCKER:
        return False
    from newb._container_runner import _default_image

    image = os.environ.get("NEWB_DOCKER_IMAGE") or _default_image()
    probe = subprocess.run(
        ["docker", "manifest", "inspect", image],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return probe.returncode == 0


_HAS_IMAGE = _runner_image_available()

requires_docker_and_key = pytest.mark.skipif(
    _OPT_OUT or not (_HAS_DOCKER and _HAS_KEY and _HAS_CREDS and _HAS_IMAGE),
    reason=(
        "e2e: needs docker on PATH, NEWB_ANTHROPIC_API_KEY set, "
        "~/.claude/.credentials.json present, AND the version-pinned "
        "newb-runner image published; skip via NEWB_SKIP_E2E=1"
    ),
)

_CANONICAL_KEYS = (
    "what_for",
    "problems_solved",
    "quick_start",
    "when_not_to_use",
    "post_install_check",
    "prompt_injection_check",
)


@pytest.fixture
def newb_repo() -> Path:
    """The repo root we're testing IN — newb itself."""
    return Path(__file__).resolve().parents[2]


def _newb_cli() -> str:
    """Locate the installed `newb` console script (matches sys.executable)."""
    p = Path(sys.executable).parent / "newb"
    if not p.is_file():
        raise FileNotFoundError(
            f"newb console script not at {p} — is newb installed in this env?"
        )
    return str(p)


def _run_newb_json(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        # Click @group consumes its options BEFORE the positional.
        [_newb_cli(), "--runs", "1", "--format", "json", str(repo)],
        capture_output=True,
        text=True,
        timeout=600,
    )


@requires_docker_and_key
def test_docker_run_against_newb_self_exits_zero(newb_repo: Path):
    # Arrange
    # Act
    proc = _run_newb_json(newb_repo)
    # Assert
    assert proc.returncode == 0, (
        f"newb exited rc={proc.returncode}\n--- STDOUT ---\n{proc.stdout[:1500]}"
        f"\n--- STDERR ---\n{proc.stderr[:1500]}"
    )


@requires_docker_and_key
def test_docker_run_report_uses_python_package_template(newb_repo: Path):
    # Arrange
    proc = _run_newb_json(newb_repo)
    # Act
    report = json.loads(proc.stdout)
    # Assert
    assert report["template"] == "python-package"


@requires_docker_and_key
@pytest.mark.parametrize("key", _CANONICAL_KEYS)
def test_docker_run_report_has_canonical_key(newb_repo: Path, key: str):
    # Arrange
    proc = _run_newb_json(newb_repo)
    report = json.loads(proc.stdout)
    # Act
    value = report.get(key)
    # Assert
    assert isinstance(value, str) and value.strip(), f"missing/empty key: {key}"


@requires_docker_and_key
def test_docker_run_does_not_report_path_mismatch(newb_repo: Path):
    # Arrange
    proc = _run_newb_json(newb_repo)
    # Act
    combined = (proc.stdout + proc.stderr).lower()
    # Assert
    assert "working directory does not exist" not in combined, (
        "host/container path mismatch — likely a stale local image. Run "
        "`docker pull ghcr.io/ywatanabe1989/newb-runner:<this-newb-version>`."
    )
