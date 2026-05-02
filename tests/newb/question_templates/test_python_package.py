"""Smoke tests for the python-package built-in question template."""

from __future__ import annotations


def test_python_package_template_has_six_canonical_keys():
    from newb.question_templates import PYTHON_PACKAGE

    assert set(PYTHON_PACKAGE) == {
        "what_for",
        "problems_solved",
        "quick_start",
        "when_not_to_use",
        "post_install_check",
        "prompt_injection_check",
    }


def test_python_package_template_prompts_are_strings_with_skills_path_placeholder():
    from newb.question_templates import PYTHON_PACKAGE

    # Every prompt is a string; at least one mentions the {skills_path}
    # placeholder so the runner's interpolation actually has work to do.
    assert all(isinstance(v, str) and v for v in PYTHON_PACKAGE.values())
    assert any("{skills_path}" in v for v in PYTHON_PACKAGE.values())


def test_get_template_round_trips_python_package():
    from newb.question_templates import PYTHON_PACKAGE, get_template

    assert get_template("python-package") is PYTHON_PACKAGE


def test_get_template_unknown_name_raises_keyerror():
    import pytest

    from newb.question_templates import get_template

    with pytest.raises(KeyError, match="unknown template"):
        get_template("does-not-exist")


def test_cli_tool_template_has_expected_keys():
    from newb.question_templates import CLI_TOOL

    assert "install_and_help" in CLI_TOOL
    assert "subcommand_tree" in CLI_TOOL
    assert "prompt_injection_check" in CLI_TOOL
