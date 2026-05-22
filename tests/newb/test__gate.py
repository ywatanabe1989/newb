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
    # Arrange
    report = _ok_report()
    # Act
    passed, _ = evaluate(report)
    # Assert
    assert passed is True


def test_default_gate_reports_no_failures_for_clean_report():
    # Arrange
    report = _ok_report()
    # Act
    _, failures = evaluate(report)
    # Assert
    assert failures == []


def test_default_gate_fails_on_install_fail():
    # Arrange
    report = _ok_report()
    report["post_install_check_parsed"]["install"] = "fail"
    # Act
    passed, _ = evaluate(report)
    # Assert
    assert passed is False


def test_default_gate_install_fail_names_install_in_failures():
    # Arrange
    report = _ok_report()
    report["post_install_check_parsed"]["install"] = "fail"
    # Act
    _, failures = evaluate(report)
    # Assert
    assert any("install" in f for f in failures)


def test_default_gate_fails_on_injection_found():
    # Arrange
    report = _ok_report()
    report["prompt_injection_check_parsed"]["found"] = True
    # Act
    passed, _ = evaluate(report)
    # Assert
    assert passed is False


def test_default_gate_injection_found_names_found_in_failures():
    # Arrange
    report = _ok_report()
    report["prompt_injection_check_parsed"]["found"] = True
    # Act
    _, failures = evaluate(report)
    # Assert
    assert any("found" in f for f in failures)


def test_missing_parsed_field_fails():
    # Arrange
    report = {"post_install_check_parsed": {"install": "ok"}}
    gate = {"post_install_check": {"install": "ok", "import": "ok"}}
    # Act
    passed, _ = evaluate(report, gate)
    # Assert
    assert passed is False


def test_missing_parsed_field_names_missing_key_in_failures():
    # Arrange
    report = {"post_install_check_parsed": {"install": "ok"}}
    gate = {"post_install_check": {"install": "ok", "import": "ok"}}
    # Act
    _, failures = evaluate(report, gate)
    # Assert
    assert any("import" in f and "missing" in f for f in failures)


def test_missing_question_section_fails():
    # Arrange
    report = {}
    # Act
    passed, _ = evaluate(report)
    # Assert
    assert passed is False


def test_missing_question_section_names_absent_in_failures():
    # Arrange
    report = {}
    # Act
    _, failures = evaluate(report)
    # Assert
    assert any("absent" in f for f in failures)


def test_list_required_means_any_of():
    # Arrange
    report = _ok_report()
    report["post_install_check_parsed"]["cli"] = "n/a"
    gate = {"post_install_check": {"install": "ok", "cli": ["ok", "n/a"]}}
    # Act
    passed, _ = evaluate(report, gate)
    # Assert
    assert passed is True


def test_runs_per_prompt_list_requires_all_pass():
    # Arrange
    report = {
        "post_install_check_parsed": [
            {"install": "ok", "import": "ok", "cli": "ok"},
            {"install": "fail", "import": "ok", "cli": "ok"},
        ],
        "prompt_injection_check_parsed": {"found": False},
    }
    # Act
    passed, _ = evaluate(report)
    # Assert
    assert passed is False


def test_runs_per_prompt_failure_names_offending_index():
    # Arrange
    report = {
        "post_install_check_parsed": [
            {"install": "ok", "import": "ok", "cli": "ok"},
            {"install": "fail", "import": "ok", "cli": "ok"},
        ],
        "prompt_injection_check_parsed": {"found": False},
    }
    # Act
    _, failures = evaluate(report)
    # Assert
    assert any("[1]" in f for f in failures)


def test_load_gate_config_uses_defaults_when_no_pyproject(tmp_path: Path):
    # Arrange
    # Act
    cfg = load_gate_config(tmp_path)
    # Assert
    assert cfg == DEFAULT_GATE


def test_load_gate_config_reads_pyproject(tmp_path: Path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [tool.newb.gate.post_install_check]
            install = "ok"
            cli = ["ok", "n/a"]
            """
        ).strip()
    )
    # Act
    cfg = load_gate_config(tmp_path)
    # Assert
    assert cfg == {"post_install_check": {"install": "ok", "cli": ["ok", "n/a"]}}
