"""Tests for newb._install._workflow against a REAL `gh` subprocess shim.

No mocks: a fake ``gh`` executable is installed on ``$PATH`` (so the
real ``subprocess.run(["gh", ...])`` in ``_gh`` runs it), driven by
two env vars the shim reads:

  - ``NEWB_TEST_GH_LOG``   : path the shim appends one argv line to per call
  - ``NEWB_TEST_GH_RULES`` : JSON [{"match": "<prefix>", "out": "<text>",
                              "rc": <int>}] — first prefix-match wins;
                              rc != 0 makes ``_gh`` raise GhError.

This exercises the real argv-building + subprocess + GhError path that a
``monkeypatch.setattr(iw, "_gh", stub)`` would have hidden.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from newb._install import _workflow as iw

_SHIM = """#!/usr/bin/env python3
import json, os, sys
log = os.environ.get("NEWB_TEST_GH_LOG")
if log:
    with open(log, "a") as f:
        f.write("\\t".join(sys.argv[1:]) + "\\n")
rules = json.loads(os.environ.get("NEWB_TEST_GH_RULES", "[]"))
joined = " ".join(sys.argv[1:])
for rule in rules:
    if joined.startswith(rule["match"]):
        sys.stdout.write(rule.get("out", ""))
        sys.exit(int(rule.get("rc", 0)))
sys.exit(0)
"""


@pytest.fixture
def gh_shim(env_set, tmp_path):
    """Install a real fake `gh` on PATH; return a helper to configure it.

    The helper exposes ``set_rules(rules)`` and ``calls()`` so tests
    drive canned responses and inspect the recorded argv lines.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(_SHIM)
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    log = tmp_path / "gh-calls.log"
    log.write_text("")
    env_set("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    env_set("NEWB_TEST_GH_LOG", str(log))
    env_set("NEWB_TEST_GH_RULES", "[]")

    class _Shim:
        def set_rules(self, rules):
            os.environ["NEWB_TEST_GH_RULES"] = json.dumps(rules)

        def calls(self):
            lines = [ln for ln in log.read_text().splitlines() if ln.strip()]
            return [tuple(ln.split("\t")) for ln in lines]

    return _Shim()


def test_secret_exists_true_when_listed(gh_shim):
    # Arrange
    gh_shim.set_rules(
        [{"match": "secret list", "out": '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'}]
    )
    # Act
    result = iw.secret_exists("o/r")
    # Assert
    assert result is True


def test_secret_exists_false_when_absent(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "secret list", "out": '[{"name": "OTHER"}]'}])
    # Act
    result = iw.secret_exists("o/r")
    # Assert
    assert result is False


def test_secret_exists_treats_gh_error_as_absent(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "secret list", "rc": 1}])
    # Act
    result = iw.secret_exists("o/r")
    # Assert
    assert result is False


def test_workflow_exists_true_when_file_present(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "out": "{...}"}])
    # Act
    result = iw.workflow_exists("o/r")
    # Assert
    assert result is True


def test_workflow_exists_false_on_gh_error(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "rc": 1}])
    # Act
    result = iw.workflow_exists("o/r")
    # Assert
    assert result is False


def test_set_secret_skips_when_existing(gh_shim):
    # Arrange
    gh_shim.set_rules(
        [{"match": "secret list", "out": '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'}]
    )
    # Act
    status = iw.set_secret("o/r", "v")
    # Assert
    assert status == "skip-existing"


def test_set_secret_makes_no_set_call_when_existing(gh_shim):
    # Arrange
    gh_shim.set_rules(
        [{"match": "secret list", "out": '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'}]
    )
    # Act
    iw.set_secret("o/r", "v")
    # Assert
    assert [c for c in gh_shim.calls() if c[:2] == ("secret", "set")] == []


def test_set_secret_writes_when_absent(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "secret list", "out": "[]"}])
    # Act
    status = iw.set_secret("o/r", "v")
    # Assert
    assert status == "set"


def test_set_secret_invokes_secret_set_with_repo_and_body(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "secret list", "out": "[]"}])
    iw.set_secret("o/r", "v")
    # Act
    set_calls = [c for c in gh_shim.calls() if c[:2] == ("secret", "set")]
    # Assert
    assert (
        len(set_calls) == 1
        and "NEWB_ANTHROPIC_API_KEY" in set_calls[0]
        and "o/r" in set_calls[0]
        and "v" in set_calls[0]
    )


def test_set_secret_force_overwrites_existing(gh_shim):
    # Arrange
    gh_shim.set_rules(
        [{"match": "secret list", "out": '[{"name": "NEWB_ANTHROPIC_API_KEY"}]'}]
    )
    # Act
    status = iw.set_secret("o/r", "v", force=True)
    # Assert
    assert status == "set"


def test_scaffold_workflow_skips_when_existing(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "out": "{...}"}])
    # Act
    status = iw.scaffold_workflow("o/r")
    # Assert
    assert status == "skip-existing"


def test_scaffold_workflow_direct_push_returns_pushed(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "rc": 1}])
    # Act
    status = iw.scaffold_workflow("o/r", push=True)
    # Assert
    assert status == "pushed"


def test_scaffold_workflow_direct_push_calls_contents_put(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "rc": 1}])
    iw.scaffold_workflow("o/r", push=True)
    # Act
    put_calls = [
        c
        for c in gh_shim.calls()
        if "PUT" in c and ".github/workflows/newb.yml" in " ".join(c)
    ]
    # Assert
    assert len(put_calls) == 1


def test_install_combines_secret_and_workflow(gh_shim):
    # Arrange
    gh_shim.set_rules(
        [
            {"match": "secret list", "out": "[]"},
            {"match": "api /repos", "rc": 1},
        ]
    )
    # Act
    out = iw.install("o/r", secret_value="v", push=True)
    # Assert
    assert out == {"secret": "set", "workflow": "pushed"}


def test_install_skips_secret_when_no_value(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "rc": 1}])
    # Act
    out = iw.install("o/r", secret_value=None, push=True)
    # Assert
    assert out["secret"] == "skip-no-value"


def test_install_makes_no_secret_set_call_when_no_value(gh_shim):
    # Arrange
    gh_shim.set_rules([{"match": "api /repos", "rc": 1}])
    iw.install("o/r", secret_value=None, push=True)
    # Act
    set_calls = [c for c in gh_shim.calls() if c[:2] == ("secret", "set")]
    # Assert
    assert set_calls == []
