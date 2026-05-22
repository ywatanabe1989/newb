"""Fast CLI happy-path smoke tests — no docker, no Anthropic.

Drive the installed `newb` console script for the introspection
surface (`--help`, `templates`, `skills`) plus the offline
``tests_newb.yaml`` parsing path. All run in well under a second; they
catch packaging / entry-point / argv-reorder breakage before the slow
e2e layer ever runs.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke


def _newb() -> str:
    p = Path(sys.executable).parent / "newb"
    if not p.is_file():
        raise FileNotFoundError(f"newb console script not at {p}")
    return str(p)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([_newb(), *args], capture_output=True, text=True, timeout=60)


def test_help_exits_zero():
    # Arrange
    # Act
    proc = _run("--help")
    # Assert
    assert proc.returncode == 0


def test_help_shows_canonical_positional_invocation():
    # Arrange
    # Act
    proc = _run("--help")
    # Assert
    assert "newb ." in proc.stdout


def test_templates_list_exits_zero():
    # Arrange
    # Act
    proc = _run("templates", "list")
    # Assert
    assert proc.returncode == 0


def test_templates_list_names_python_package():
    # Arrange
    # Act
    proc = _run("templates", "list")
    # Assert
    assert "python-package" in proc.stdout


def test_list_python_apis_exits_zero():
    # Arrange
    # Act
    proc = _run("list-python-apis")
    # Assert
    assert proc.returncode == 0


def test_tests_newb_yaml_parses_via_loader(tmp_path):
    # Arrange
    yaml = pytest.importorskip("yaml")  # noqa: F841 — guard the optional dep
    from newb._grading import _load_tests

    (tmp_path / "tests_newb.yaml").write_text(
        "- name: smoke_entry\n  prompt: What is this?\n  expect_contains: ['demo']\n"
    )
    # Act
    entries = _load_tests(tmp_path)
    # Assert
    assert entries[0]["name"] == "smoke_entry"
