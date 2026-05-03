"""Tests for newb._gate — declarative CI gate evaluation."""

from __future__ import annotations

import textwrap
from pathlib import Path

from newb._gate import DEFAULT_GATE, evaluate, load_gate_config


def _ok_report() -> dict:
    return {
        "post_install_check_parsed": {
            "install": "ok",
            "import": "ok",
            "cli": "ok",
        },
        "prompt_injection_check_parsed": {"found": False, "found_raw": "no"},
    }


def test_default_gate_passes_clean_report():
    passed, failures = evaluate(_ok_report())
    assert passed is True
    assert failures == []


def test_default_gate_fails_on_install_fail():
    r = _ok_report()
    r["post_install_check_parsed"]["install"] = "fail"
    passed, failures = evaluate(r)
    assert passed is False
    assert any("install" in f for f in failures)


def test_default_gate_fails_on_injection_found():
    r = _ok_report()
    r["prompt_injection_check_parsed"]["found"] = True
    passed, failures = evaluate(r)
    assert passed is False
    assert any("found" in f for f in failures)


def test_missing_parsed_field_fails_loudly():
    r = {"post_install_check_parsed": {"install": "ok"}}  # missing import
    passed, failures = evaluate(
        r, {"post_install_check": {"install": "ok", "import": "ok"}}
    )
    assert passed is False
    assert any("import" in f and "missing" in f for f in failures)


def test_missing_question_section_fails():
    r = {}
    passed, failures = evaluate(r)
    assert passed is False
    assert any("absent" in f for f in failures)


def test_list_required_means_any_of():
    r = _ok_report()
    r["post_install_check_parsed"]["cli"] = "n/a"
    passed, _ = evaluate(
        r,
        {"post_install_check": {"install": "ok", "cli": ["ok", "n/a"]}},
    )
    assert passed is True


def test_runs_per_prompt_list_requires_all_pass():
    r = {
        "post_install_check_parsed": [
            {"install": "ok", "import": "ok", "cli": "ok"},
            {"install": "fail", "import": "ok", "cli": "ok"},
        ],
        "prompt_injection_check_parsed": {"found": False},
    }
    passed, failures = evaluate(r)
    assert passed is False
    assert any("[1]" in f for f in failures)


def test_load_gate_config_uses_defaults_when_no_pyproject(tmp_path: Path):
    cfg = load_gate_config(tmp_path)
    assert cfg == DEFAULT_GATE


def test_load_gate_config_reads_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.newb.gate.post_install_check]
            install = "ok"
            cli = ["ok", "n/a"]
            """
        ).strip()
    )
    cfg = load_gate_config(tmp_path)
    assert cfg == {"post_install_check": {"install": "ok", "cli": ["ok", "n/a"]}}


# EOF
