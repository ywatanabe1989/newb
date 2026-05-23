"""Tests for newb._try.

The runner collaborator is injected through the documented ``_runner=``
kwarg on ``newb.run`` — no module patching needed. ``_FakeRunner`` /
``_JudgeRunner`` are hand-rolled recording fakes that expose only the
``.run(prompt, *, model, timeout) -> {"result": text}`` + ``.close()``
contract that production touches.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Smoke — public symbol surface. Split per attribute so a single failure
# names the broken symbol.
# ---------------------------------------------------------------------------


def test_newb_top_level_exports_render_markdown_callable():
    # Arrange
    import newb

    # Act
    callable_ = callable(newb.render_markdown)
    # Assert
    assert callable_


def test_newb_top_level_exports_run_callable():
    # Arrange
    import newb

    # Act
    callable_ = callable(newb.run)
    # Assert
    assert callable_


def test_newb_module_itself_is_callable_via_pep562():
    """Module is callable as a shortcut for newb.run (PEP 562 trick)."""
    # Arrange
    import newb

    # Act
    callable_ = callable(newb)
    # Assert
    assert callable_


def test_newb_removed_self_explain_attribute_is_absent():
    """`self_explain` was the deprecated alias — removed in 0.12.0."""
    # Arrange
    import newb

    # Act
    present = hasattr(newb, "self_explain")
    # Assert
    assert present is False


def test_newb_all_does_not_export_self_explain():
    # Arrange
    import newb

    # Act
    present = "self_explain" in newb.__all__
    # Assert
    assert present is False


def test_newb_version_is_non_empty_string():
    """Version is resolved dynamically from importlib.metadata in
    __init__.py, so just check the shape — not pin to a literal that
    would drift with every release."""
    # Arrange
    import newb

    # Act
    v = newb.__version__
    # Assert
    assert isinstance(v, str) and v


@pytest.mark.parametrize(
    "key", ["what_for", "problems_solved", "quick_start", "when_not_to_use"]
)
def test_python_package_template_key_is_str(key):
    # Arrange
    from newb.question_templates import PYTHON_PACKAGE

    # Act
    value = PYTHON_PACKAGE[key]
    # Assert
    assert isinstance(value, str)


# ---------------------------------------------------------------------------
# Run end-to-end with a hand-rolled fake runner.
# ---------------------------------------------------------------------------


class _FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, prompt, *, model="claude-haiku-4-5", timeout=120):
        self.calls.append((prompt, model))
        if "ONE sentence" in prompt:
            return {"result": "It loads and saves data in 30+ formats."}
        if "3-5 problems" in prompt:
            return {
                "result": (
                    "| # | Problem | Solution |\n"
                    "|---|---------|----------|\n"
                    "| 1 | Format zoo | One save() call |\n"
                )
            }
        if "minimal working example" in prompt:
            return {"result": "```python\nimport mypkg\n```"}
        if "NOT use this package" in prompt:
            return {"result": "Don't use this for parallel execution."}
        return {"result": "unexpected prompt"}

    def close(self):
        pass


def _make_skills(tmp_path):
    skills = tmp_path / "mypkg"
    skills.mkdir()
    (skills / "SKILL.md").write_text("# mypkg\nA demo package.\n")
    return skills


@pytest.fixture
def _run_with_fake_runner(tmp_path):
    """Stage a skills dir, run() it with _FakeRunner, return (result, runner)."""
    from newb import run

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    return run(skills, _runner=runner), runner


def test_run_returns_package_name(_run_with_fake_runner):
    # Arrange
    result, _ = _run_with_fake_runner
    # Act
    value = result["package"]
    # Assert
    assert value == "mypkg"


@pytest.mark.parametrize(
    "key", ["what_for", "problems_solved", "quick_start", "when_not_to_use"]
)
def test_run_result_has_canonical_key(_run_with_fake_runner, key):
    # Arrange
    result, _ = _run_with_fake_runner
    # Act
    present = key in result
    # Assert
    assert present


def test_run_what_for_contains_fake_runner_phrase(_run_with_fake_runner):
    # Arrange
    result, _ = _run_with_fake_runner
    # Act
    present = "30+ formats" in result["what_for"]
    # Assert
    assert present


def test_run_problems_solved_includes_table_header(_run_with_fake_runner):
    # Arrange
    result, _ = _run_with_fake_runner
    # Act
    present = "| # | Problem | Solution |" in result["problems_solved"]
    # Assert
    assert present


def test_run_quick_start_renders_import_block(_run_with_fake_runner):
    # Arrange
    result, _ = _run_with_fake_runner
    # Act
    present = "import mypkg" in result["quick_start"]
    # Assert
    assert present


def test_run_invokes_runner_once_per_template_prompt(_run_with_fake_runner):
    """python-package template now has 6 prompts (added post_install_check
    + prompt_injection_check that leverage the full-perms container)."""
    # Arrange
    _, runner = _run_with_fake_runner
    from newb.question_templates import PYTHON_PACKAGE

    # Act
    count = len(runner.calls)
    # Assert
    assert count == len(PYTHON_PACKAGE)


def test_run_uses_default_model_for_every_call(_run_with_fake_runner):
    # Arrange
    _, runner = _run_with_fake_runner
    # Act
    models = {call[1] for call in runner.calls}
    # Assert
    assert models == {"claude-haiku-4-5"}


# ---------------------------------------------------------------------------
# runs_per_prompt > 1 produces lists.
# ---------------------------------------------------------------------------


@pytest.fixture
def _run_with_runs_per_prompt_two(tmp_path):
    from newb import run

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    return run(skills, runs_per_prompt=2, _runner=runner), runner


def test_runs_per_prompt_returns_list_per_question(_run_with_runs_per_prompt_two):
    # Arrange
    result, _ = _run_with_runs_per_prompt_two
    # Act
    value = result["what_for"]
    # Assert
    assert isinstance(value, list)


def test_runs_per_prompt_list_length_matches_runs(_run_with_runs_per_prompt_two):
    # Arrange
    result, _ = _run_with_runs_per_prompt_two
    # Act
    length = len(result["what_for"])
    # Assert
    assert length == 2


def test_runs_per_prompt_total_runner_calls_scales(_run_with_runs_per_prompt_two):
    # Arrange
    _, runner = _run_with_runs_per_prompt_two
    from newb.question_templates import PYTHON_PACKAGE

    # Act
    count = len(runner.calls)
    # Assert
    assert count == len(PYTHON_PACKAGE) * 2


def test_run_accepts_string_path(tmp_path):
    # Arrange
    from newb import run

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    # Act
    result = run(str(skills), _runner=runner)
    # Assert
    assert result["package"] == "mypkg"


def test_run_missing_dir_raises():
    # Arrange
    from newb import run

    # Act
    ctx = pytest.raises(FileNotFoundError)
    # Assert
    with ctx:
        run("/nonexistent/path/__no__")


def test_run_no_md_files_raises(tmp_path):
    # Arrange
    from newb import run

    empty = tmp_path / "empty"
    empty.mkdir()
    # Act
    ctx = pytest.raises(FileNotFoundError)
    # Assert
    with ctx:
        run(empty)


# ---------------------------------------------------------------------------
# render_markdown — pin each header line separately.
# ---------------------------------------------------------------------------


@pytest.fixture
def _rendered_markdown(tmp_path):
    from newb import render_markdown, run

    skills = _make_skills(tmp_path)
    result = run(skills, _runner=_FakeRunner())
    return render_markdown(result)


@pytest.mark.parametrize(
    "snippet",
    [
        "## Skills Quality (verified by agent)",
        "Package: `mypkg`",
        "**Q: What is this package for?**",
        "**Q: What problems does it solve?**",
        "**Q: How do I use it?**",
        "**Q: When should I NOT use this?**",
    ],
)
def test_render_markdown_contains_section_marker(_rendered_markdown, snippet):
    # Arrange
    md = _rendered_markdown
    # Act
    present = snippet in md
    # Assert
    assert present


def test_render_markdown_ends_with_trailing_newline(_rendered_markdown):
    # Arrange
    md = _rendered_markdown
    # Act
    trails = md.endswith("\n")
    # Assert
    assert trails


# ---------------------------------------------------------------------------
# tests_newb.yaml + tests_newb.py loaders.
# ---------------------------------------------------------------------------


def test_load_tests_missing_file_returns_empty(tmp_path):
    # Arrange
    from newb._try import _load_tests

    # Act
    out = _load_tests(tmp_path)
    # Assert
    assert out == []


@pytest.fixture
def _yaml_tests_parsed(tmp_path):
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text(
        "- name: pkg_purpose\n"
        "  prompt: What is this?\n"
        "  expect_contains: ['No', 'scitex-parallel']\n"
        "  expect_excludes: ['yes you can']\n"
    )
    return _load_tests(tmp_path)


def test_load_tests_parses_one_entry(_yaml_tests_parsed):
    # Arrange
    rs = _yaml_tests_parsed
    # Act
    count = len(rs)
    # Assert
    assert count == 1


def test_load_tests_parses_entry_name(_yaml_tests_parsed):
    # Arrange
    rs = _yaml_tests_parsed
    # Act
    value = rs[0]["name"]
    # Assert
    assert value == "pkg_purpose"


def test_load_tests_parses_entry_prompt(_yaml_tests_parsed):
    # Arrange
    rs = _yaml_tests_parsed
    # Act
    value = rs[0]["prompt"]
    # Assert
    assert value == "What is this?"


def test_load_tests_parses_entry_expect_contains_includes_token(_yaml_tests_parsed):
    # Arrange
    rs = _yaml_tests_parsed
    # Act
    present = "scitex-parallel" in rs[0]["expect_contains"]
    # Assert
    assert present


def test_load_tests_invalid_yaml_returns_empty(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text("not: a list: just: garbage:")
    # Act
    out = _load_tests(tmp_path)
    # Assert
    assert out == []


@pytest.fixture
def _python_tests_parsed(tmp_path):
    """tests_newb.py with TESTS list is discovered alongside YAML."""
    from newb._try import _load_tests

    (tmp_path / "tests_newb.py").write_text(
        "TESTS = [\n"
        '    {"name": "py_one", "prompt": "What does it do?",\n'
        '     "expect_contains": ["foo"]},\n'
        '    {"prompt": "Edge case?", "judge": "Must mention X"},\n'
        "]\n"
    )
    return _load_tests(tmp_path)


def test_load_tests_python_module_parses_two_entries(_python_tests_parsed):
    # Arrange
    rs = _python_tests_parsed
    # Act
    count = len(rs)
    # Assert
    assert count == 2


def test_load_tests_python_module_preserves_explicit_name(_python_tests_parsed):
    # Arrange
    rs = _python_tests_parsed
    # Act
    value = rs[0]["name"]
    # Assert
    assert value == "py_one"


def test_load_tests_python_module_preserves_expect_contains(_python_tests_parsed):
    # Arrange
    rs = _python_tests_parsed
    # Act
    value = rs[0]["expect_contains"]
    # Assert
    assert value == ["foo"]


def test_load_tests_python_module_auto_names_unnamed_entry(_python_tests_parsed):
    # Arrange
    rs = _python_tests_parsed
    # Act
    value = rs[1]["name"]
    # Assert
    assert value == "tests_newb_1"


def test_load_tests_python_module_preserves_judge_field(_python_tests_parsed):
    # Arrange
    rs = _python_tests_parsed
    # Act
    value = rs[1]["judge"]
    # Assert
    assert value == "Must mention X"


@pytest.fixture
def _glob_python_and_yaml_tests(tmp_path):
    """test_newb_*.py files are also picked up; YAML + .py concat."""
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text(
        "- name: yaml_one\n  prompt: From YAML\n"
    )
    (tmp_path / "test_newb_extra.py").write_text(
        'TESTS = [{"name": "py_extra", "prompt": "From extra .py"}]\n'
    )
    return {r["name"] for r in _load_tests(tmp_path)}


def test_load_tests_pytest_style_glob_includes_yaml_entry(_glob_python_and_yaml_tests):
    # Arrange
    names = _glob_python_and_yaml_tests
    # Act
    present = "yaml_one" in names
    # Assert
    assert present


def test_load_tests_pytest_style_glob_includes_python_entry(
    _glob_python_and_yaml_tests,
):
    # Arrange
    names = _glob_python_and_yaml_tests
    # Act
    present = "py_extra" in names
    # Assert
    assert present


def test_load_tests_python_missing_TESTS_returns_empty(tmp_path):
    """A test_newb_*.py without a TESTS list contributes zero entries."""
    # Arrange
    from newb._try import _load_tests

    (tmp_path / "tests_newb.py").write_text("# no TESTS defined\nx = 1\n")
    # Act
    out = _load_tests(tmp_path)
    # Assert
    assert out == []


def test_load_tests_accepts_judge_field(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text(
        "- name: redirect_check\n"
        "  prompt: How do I do parallel?\n"
        "  judge: Must say not supported and recommend an alternative.\n"
    )
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs[0]["judge"].startswith("Must say")


class _JudgeRunner:
    """Runner that returns canned answers + a PASS/FAIL judge verdict."""

    def __init__(
        self, answer="The package does not support parallel.", verdict="PASS: ok"
    ):
        self.answer = answer
        self.verdict = verdict
        self.calls = []

    def run(self, prompt, *, model="claude-haiku-4-5", timeout=120):
        self.calls.append(prompt)
        if "CRITERIA" in prompt:
            return {"result": self.verdict}
        return {"result": self.answer}

    def close(self):
        pass


# ---------------------------------------------------------------------------
# Author-tests pass/fail bookkeeping.
# ---------------------------------------------------------------------------


@pytest.fixture
def _run_with_two_passing_yaml_tests(tmp_path):
    pytest.importorskip("yaml")
    from newb import run

    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: contains_check\n"
        "  prompt: Anything?\n"
        "  expect_contains: ['parallel']\n"
        "- name: judge_check\n"
        "  prompt: Anything else?\n"
        "  judge: Must say no parallel.\n"
    )
    runner = _JudgeRunner()
    return run(skills, _runner=runner)


def test_run_with_yaml_tests_records_tests_block(_run_with_two_passing_yaml_tests):
    # Arrange
    result = _run_with_two_passing_yaml_tests
    # Act
    present = "tests" in result
    # Assert
    assert present


def test_run_with_yaml_tests_records_tests_summary_block(
    _run_with_two_passing_yaml_tests,
):
    # Arrange
    result = _run_with_two_passing_yaml_tests
    # Act
    present = "tests_summary" in result
    # Assert
    assert present


def test_run_with_yaml_tests_total_matches_count(_run_with_two_passing_yaml_tests):
    # Arrange
    result = _run_with_two_passing_yaml_tests
    # Act
    value = result["tests_summary"]["total"]
    # Assert
    assert value == 2


def test_run_with_yaml_tests_passed_matches_count(_run_with_two_passing_yaml_tests):
    # Arrange
    result = _run_with_two_passing_yaml_tests
    # Act
    value = result["tests_summary"]["passed"]
    # Assert
    assert value == 2


def test_run_with_yaml_tests_does_not_emit_deprecated_red_tests_alias(
    _run_with_two_passing_yaml_tests,
):
    """back-compat alias removed in 0.12.0"""
    # Arrange
    result = _run_with_two_passing_yaml_tests
    # Act
    present = "red_tests" in result
    # Assert
    assert present is False


@pytest.fixture
def _run_with_judge_fail(tmp_path):
    pytest.importorskip("yaml")
    from newb import run

    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: judge_check\n  prompt: Q\n  judge: criteria\n"
    )
    runner = _JudgeRunner(verdict="FAIL: not enough detail")
    return run(skills, _runner=runner)


def test_run_judge_fail_summary_passed_is_zero(_run_with_judge_fail):
    # Arrange
    result = _run_with_judge_fail
    # Act
    value = result["tests_summary"]["passed"]
    # Assert
    assert value == 0


def test_run_judge_fail_per_test_judge_passed_is_false(_run_with_judge_fail):
    # Arrange
    result = _run_with_judge_fail
    # Act
    value = result["tests"][0]["judge"]["passed"]
    # Assert
    assert value is False


# ---------------------------------------------------------------------------
# _stage_skills_mount isolation.
# ---------------------------------------------------------------------------


@pytest.fixture
def _staged_skills_mount(tmp_path):
    import shutil

    from newb._try import _stage_skills_mount

    src = tmp_path / "src"
    src.mkdir()
    (src / "01_quick-start.md").write_text("# Quick Start\n")
    mount = _stage_skills_mount(src, "demo-pkg")
    try:
        yield mount
    finally:
        shutil.rmtree(mount, ignore_errors=True)


def test_stage_skills_mount_copies_md_file_under_target(_staged_skills_mount):
    # Arrange
    mount = _staged_skills_mount
    copied = mount / ".claude" / "skills" / "demo-pkg"
    # Act
    is_file = (copied / "01_quick-start.md").is_file()
    # Assert
    assert is_file


def test_stage_skills_mount_skills_root_contains_only_target_dir(_staged_skills_mount):
    # Arrange
    mount = _staged_skills_mount
    skills_root = mount / ".claude" / "skills"
    # Act
    children = sorted(p.name for p in skills_root.iterdir())
    # Assert
    assert children == ["demo-pkg"]


def test_stage_skills_mount_top_level_contains_only_claude_dir(_staged_skills_mount):
    # Arrange
    mount = _staged_skills_mount
    # Act
    children = sorted(p.name for p in mount.iterdir())
    # Assert
    assert children == [".claude"]


# ---------------------------------------------------------------------------
# CLI surface.
# ---------------------------------------------------------------------------


@pytest.fixture
def _cli_help_result():
    """pytest-style top-level: `newb <target>` is THE primary form.
    All the canonical flags + the example block live on the group's
    own --help (no subcommand needed for the try-action)."""
    from click.testing import CliRunner

    from newb._cli import main

    return CliRunner().invoke(main, ["--help"])


def test_cli_help_exits_zero(_cli_help_result):
    # Arrange
    result = _cli_help_result
    # Act
    rc = result.exit_code
    # Assert
    assert rc == 0


def test_cli_help_shows_example_section_header(_cli_help_result):
    # Arrange
    result = _cli_help_result
    # Act
    present = "Example" in result.output
    # Assert
    assert present


def test_cli_help_shows_canonical_positional_invocation(_cli_help_result):
    # Arrange
    result = _cli_help_result
    # Act
    present = "newb ." in result.output
    # Assert
    assert present


def test_cli_help_shows_format_flag(_cli_help_result):
    # Arrange
    result = _cli_help_result
    # Act
    present = "--format" in result.output
    # Assert
    assert present


def test_cli_help_shows_template_flag(_cli_help_result):
    # Arrange
    result = _cli_help_result
    # Act
    present = "--template" in result.output
    # Assert
    assert present
