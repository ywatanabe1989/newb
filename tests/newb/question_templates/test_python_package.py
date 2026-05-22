"""Tests for the built-in question templates."""

from __future__ import annotations

import pytest

from newb.question_templates import (
    CLI_TOOL,
    PYTHON_PACKAGE,
    get_template,
)


def test_python_package_template_has_six_canonical_keys():
    # Arrange
    expected = {
        "what_for",
        "problems_solved",
        "quick_start",
        "when_not_to_use",
        "post_install_check",
        "prompt_injection_check",
    }
    # Act
    keys = set(PYTHON_PACKAGE)
    # Assert
    assert keys == expected


def test_python_package_prompts_are_non_empty_strings():
    # Arrange
    # Act
    all_strings = all(isinstance(v, str) and v for v in PYTHON_PACKAGE.values())
    # Assert
    assert all_strings


def test_python_package_at_least_one_prompt_uses_skills_path_placeholder():
    # Arrange
    # Act
    has_placeholder = any("{skills_path}" in v for v in PYTHON_PACKAGE.values())
    # Assert
    assert has_placeholder


def test_get_template_round_trips_python_package():
    # Arrange
    # Act
    resolved = get_template("python-package")
    # Assert
    assert resolved is PYTHON_PACKAGE


def test_get_template_unknown_name_raises_keyerror():
    # Arrange
    ctx = pytest.raises(KeyError, match="unknown template")
    # Act
    # Assert
    with ctx:
        get_template("does-not-exist")


@pytest.mark.parametrize(
    "key", ["install_and_help", "subcommand_tree", "prompt_injection_check"]
)
def test_cli_tool_template_has_expected_key(key):
    # Arrange
    # Act
    present = key in CLI_TOOL
    # Assert
    assert present
