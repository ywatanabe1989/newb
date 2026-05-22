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

The :func:`env_save_restore` fixture is the canonical replacement for
``monkeypatch.setenv`` / ``monkeypatch.delenv`` under the SciTeX
no-mocks rule (PA-306, STX-NM002): the fixture snapshots ``os.environ``,
yields it for direct mutation by the test, and restores on teardown.
See ``~/.claude/skills/scitex/general/02_package_12_no-mocks.md``.
"""

from __future__ import annotations

import os
import stat
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
# Shared fixtures (no-mocks campaign — replaces monkeypatch idioms)
# ---------------------------------------------------------------------------


@pytest.fixture
def env_save_restore():
    """Snapshot ``os.environ``; restore on teardown.

    Canonical no-mocks replacement for ``monkeypatch.setenv`` /
    ``monkeypatch.delenv``. Tests mutate ``os.environ`` directly; this
    fixture guarantees the mutation does not leak across tests.

    Yields
    ------
    os._Environ
        The live ``os.environ`` mapping. Mutate via ``[]=`` / ``pop()``
        / ``update()`` as normal.
    """
    saved = dict(os.environ)
    try:
        yield os.environ
    finally:
        os.environ.clear()
        os.environ.update(saved)


@pytest.fixture
def fake_runtime_bin(tmp_path, env_save_restore):
    """Write empty-but-executable ``docker`` / ``podman`` / ``apptainer``
    fakes into ``tmp_path/bin`` and prepend it to ``$PATH``.

    Production code under test calls ``shutil.which(self.runtime_bin)``
    to refuse construction when the runtime is absent; the fakes are
    enough to satisfy that check. The fakes are never actually invoked
    by the tests in this file — only ``_build_argv()`` is exercised,
    which is a pure string-building method.

    This replaces the previous ``monkeypatch.setattr(shutil, 'which',
    lambda _: '/usr/bin/fake')`` idiom (STX-NM002 / PA-306).

    Returns
    -------
    pathlib.Path
        The ``tmp_path/bin`` directory containing the shims.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("docker", "podman", "apptainer"):
        binary = bin_dir / name
        binary.write_text("#!/usr/bin/env bash\nexit 0\n")
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    env_save_restore["PATH"] = f"{bin_dir}:{env_save_restore.get('PATH', '')}"
    return bin_dir
