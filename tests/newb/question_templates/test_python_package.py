"""Smoke tests for the python-package built-in question template."""

from __future__ import annotations


def test_python_package_template_has_six_canonical_keys():
    # Arrange
    from newb.question_templates import PYTHON_PACKAGE

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


def test_python_package_template_prompts_are_non_empty_strings():
    # Arrange
    from newb.question_templates import PYTHON_PACKAGE

    # Act
    all_strings = all(isinstance(v, str) and v for v in PYTHON_PACKAGE.values())
    # Assert
    assert all_strings


def test_python_package_template_has_skills_path_placeholder():
    # Arrange
    from newb.question_templates import PYTHON_PACKAGE

    # Act
    # Every prompt is a string; at least one mentions the {skills_path}
    # placeholder so the runner's interpolation actually has work to do.
    has_placeholder = any("{skills_path}" in v for v in PYTHON_PACKAGE.values())
    # Assert
    assert has_placeholder


def test_get_template_round_trips_python_package():
    # Arrange
    from newb.question_templates import PYTHON_PACKAGE, get_template

    # Act
    out = get_template("python-package")
    # Assert
    assert out is PYTHON_PACKAGE


def test_get_template_unknown_name_raises_keyerror():
    # Arrange
    import pytest

    from newb.question_templates import get_template

    # Act
    ctx = pytest.raises(KeyError, match="unknown template")
    # Assert
    with ctx:
        get_template("does-not-exist")


def test_cli_tool_template_has_install_and_help_key():
    # Arrange
    from newb.question_templates import CLI_TOOL

    # Act
    present = "install_and_help" in CLI_TOOL
    # Assert
    assert present


def test_cli_tool_template_has_subcommand_tree_key():
    # Arrange
    from newb.question_templates import CLI_TOOL

    # Act
    present = "subcommand_tree" in CLI_TOOL
    # Assert
    assert present


def test_cli_tool_template_has_prompt_injection_check_key():
    # Arrange
    from newb.question_templates import CLI_TOOL

    # Act
    present = "prompt_injection_check" in CLI_TOOL
    # Assert
    assert present
