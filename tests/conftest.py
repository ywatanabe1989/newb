"""Pytest fixtures + module-import-time subprocess-coverage wiring.

An empty conftest.py at tests/ is the canonical SciTeX convention
(audit-project PS208) — it pins the pytest rootdir and gives downstream
fixtures a home.

In addition, this file wires up subprocess coverage per scitex-dev skill
leaf `05_development_06_subprocess-coverage.md`. `newb` spawns child
Python interpreters (container runners, `subprocess.run([sys.executable,
...])` smoke checks) whose coverage data is otherwise dropped by the
default pytest-cov setup, because pytest-cov has already pinned
`COVERAGE_FILE` to a per-test tmp dir before this conftest loads. We
**force-set** (not `setdefault` — that's a silent no-op) the canonical
env vars and drop an idempotent `.pth` shim into site-packages so
`coverage.process_startup()` runs in every child.
"""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def env_set():
    """Set env vars for the duration of a test; restore on teardown.

    Yield-based replacement for ``monkeypatch.setenv`` (no-mocks rule:
    ``scitex/general/02_package_12_no-mocks.md``). Call ``env_set(KEY,
    VALUE)`` any number of times; every touched key is restored to its
    prior value (or removed if it was unset) when the test finishes.
    """
    saved: dict[str, str | None] = {}

    def _set(key: str, value: str) -> None:
        if key not in saved:
            saved[key] = os.environ.get(key)
        os.environ[key] = value

    try:
        yield _set
    finally:
        for key, prev in saved.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev


# Pin coverage's data file at the repo root and point process_startup
# at our pyproject so child interpreters configure themselves correctly.
os.environ["COVERAGE_PROCESS_START"] = str(_PROJECT_ROOT / "pyproject.toml")
os.environ["COVERAGE_FILE"] = str(_PROJECT_ROOT / ".coverage")


def _ensure_subprocess_coverage_shim() -> None:
    """Drop an idempotent `.pth` file in site-packages that auto-starts
    coverage in every child Python interpreter via
    ``coverage.process_startup()``.
    """
    purelib = Path(sysconfig.get_paths()["purelib"])
    pth = purelib / "_newb_subprocess_coverage.pth"
    shim = (
        "import os, coverage\n"
        "if os.environ.get('COVERAGE_PROCESS_START'):\n"
        "    coverage.process_startup()\n"
    )
    try:
        if not pth.exists() or pth.read_text() != shim:
            pth.write_text(shim)
    except OSError:
        # site-packages may be read-only (e.g. system Python); silently
        # skip — local dev venvs are writable and that's where this matters.
        pass


_ensure_subprocess_coverage_shim()
