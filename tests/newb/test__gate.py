"""Tests for newb._gate — declarative CI gate evaluation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

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


@pytest.fixture
def _clean_report_eval() -> tuple[bool, list[str]]:
    return evaluate(_ok_report())


def test_default_gate_passes_clean_report(_clean_report_eval):
    # Arrange
    passed, _ = _clean_report_eval
    # Act
    result = passed
    # Assert
    assert result is True


def test_default_gate_passes_clean_report_yields_no_failures(_clean_report_eval):
    # Arrange
    _, failures = _clean_report_eval
    # Act
    result = failures
    # Assert
    assert result == []


@pytest.fixture
def _install_fail_eval() -> tuple[bool, list[str]]:
    r = _ok_report()
    r["post_install_check_parsed"]["install"] = "fail"
    return evaluate(r)


def test_default_gate_fails_on_install_fail(_install_fail_eval):
    # Arrange
    passed, _ = _install_fail_eval
    # Act
    result = passed
    # Assert
    assert result is False


def test_default_gate_install_fail_failure_message_mentions_install(_install_fail_eval):
    # Arrange
    _, failures = _install_fail_eval
    # Act
    matched = any("install" in f for f in failures)
    # Assert
    assert matched


@pytest.fixture
def _injection_found_eval() -> tuple[bool, list[str]]:
    r = _ok_report()
    r["prompt_injection_check_parsed"]["found"] = True
    return evaluate(r)


def test_default_gate_fails_on_injection_found(_injection_found_eval):
    # Arrange
    passed, _ = _injection_found_eval
    # Act
    result = passed
    # Assert
    assert result is False


def test_default_gate_injection_found_message_mentions_found(_injection_found_eval):
    # Arrange
    _, failures = _injection_found_eval
    # Act
    matched = any("found" in f for f in failures)
    # Assert
    assert matched


@pytest.fixture
def _missing_parsed_field_eval() -> tuple[bool, list[str]]:
    r = {"post_install_check_parsed": {"install": "ok"}}  # missing import
    return evaluate(
        r, {"post_install_check": {"install": "ok", "import": "ok"}}
    )


def test_missing_parsed_field_fails(_missing_parsed_field_eval):
    # Arrange
    passed, _ = _missing_parsed_field_eval
    # Act
    result = passed
    # Assert
    assert result is False


def test_missing_parsed_field_failure_message_calls_it_out(_missing_parsed_field_eval):
    # Arrange
    _, failures = _missing_parsed_field_eval
    # Act
    matched = any("import" in f and "missing" in f for f in failures)
    # Assert
    assert matched


@pytest.fixture
def _missing_section_eval() -> tuple[bool, list[str]]:
    return evaluate({})


def test_missing_question_section_fails(_missing_section_eval):
    # Arrange
    passed, _ = _missing_section_eval
    # Act
    result = passed
    # Assert
    assert result is False


def test_missing_question_section_failure_message_is_absent(_missing_section_eval):
    # Arrange
    _, failures = _missing_section_eval
    # Act
    matched = any("absent" in f for f in failures)
    # Assert
    assert matched


def test_list_required_means_any_of():
    # Arrange
    r = _ok_report()
    r["post_install_check_parsed"]["cli"] = "n/a"
    # Act
    passed, _ = evaluate(
        r,
        {"post_install_check": {"install": "ok", "cli": ["ok", "n/a"]}},
    )
    # Assert
    assert passed is True


def test_runs_per_prompt_list_requires_all_pass():
    """When a question's parsed value is a list (runs_per_prompt > 1),
    the gate must fail if ANY run fails — and the failure must
    identify which run by index."""
    # Arrange
    r = {
        "post_install_check_parsed": [
            {"install": "ok", "import": "ok", "cli": "ok"},
            {"install": "fail", "import": "ok", "cli": "ok"},
        ],
        "prompt_injection_check_parsed": {"found": False},
    }
    # Act
    passed, failures = evaluate(r)
    # Assert
    assert passed is False and any("[1]" in f for f in failures)


def test_load_gate_config_uses_defaults_when_no_pyproject(tmp_path: Path):
    # Arrange
    start = tmp_path
    # Act
    cfg = load_gate_config(start)
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


# EOF
