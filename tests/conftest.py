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


# ---------------------------------------------------------------------------
# Real-collaborator fixtures (no-mocks discipline — see PA-306 / STX-NM00*).
# Replace `monkeypatch.setenv(...)` usage with this yield-based fixture so
# the production code path stays exercised (real `os.environ` read), and
# the test's mutations are snapshotted + restored honestly across teardown.
# ---------------------------------------------------------------------------
@pytest.fixture
def env_save_restore():
    """Snapshot ``os.environ`` and restore it at teardown.

    Yields a setter helper: ``env(name, value=None)``.
    ``value=None`` deletes the var (think ``monkeypatch.delenv``).
    Use this instead of `monkeypatch.setenv` / `.delenv` — the
    no-mocks rule bans the `monkeypatch` fixture entirely.
    """
    saved = dict(os.environ)

    def setter(name: str, value: str | None = None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value

    try:
        yield setter
    finally:
        # Restore in two passes: drop additions, then put back originals.
        for k in list(os.environ.keys()):
            if k not in saved:
                del os.environ[k]
        for k, v in saved.items():
            os.environ[k] = v
