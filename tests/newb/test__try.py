"""Tests for newb._try.

The agent / docker boundary is replaced by hand-rolled fake runners
injected through the ``_runner=`` test seam (no mocks — real objects
exercising the real ``run`` orchestration).
"""

from __future__ import annotations

import shutil

import pytest

from newb import render_markdown, run
from newb._try import _load_tests, _stage_skills_mount
from newb.question_templates import PYTHON_PACKAGE


# ---------------------------------------------------------------------------
# Hand-rolled fakes (injected via the `_runner=` seam)
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


class _JudgeRunner:
    """Runner returning canned answers + a PASS/FAIL judge verdict."""

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


def _make_skills(tmp_path):
    skills = tmp_path / "mypkg"
    skills.mkdir()
    (skills / "SKILL.md").write_text("# mypkg\nA demo package.\n")
    return skills


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_module_exposes_callable_run():
    # Arrange
    import newb

    # Act
    is_callable = callable(newb.run)
    # Assert
    assert is_callable


def test_module_itself_is_callable_shortcut():
    # Arrange
    import newb

    # Act
    is_callable = callable(newb)
    # Assert
    assert is_callable


def test_deprecated_self_explain_alias_removed():
    # Arrange
    import newb

    # Act
    present = hasattr(newb, "self_explain")
    # Assert
    assert not present


def test_version_is_a_non_empty_string():
    # Arrange
    import newb

    # Act
    version = newb.__version__
    # Assert
    assert isinstance(version, str) and version


# ---------------------------------------------------------------------------
# run() with an injected fake runner
# ---------------------------------------------------------------------------


def test_run_reports_package_name(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    # Act
    result = run(skills, _runner=_FakeRunner())
    # Assert
    assert result["package"] == "mypkg"


def test_run_carries_what_for_answer(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    # Act
    result = run(skills, _runner=_FakeRunner())
    # Assert
    assert "30+ formats" in result["what_for"]


def test_run_carries_problems_table(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    # Act
    result = run(skills, _runner=_FakeRunner())
    # Assert
    assert "| # | Problem | Solution |" in result["problems_solved"]


def test_run_carries_quick_start_code(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    # Act
    result = run(skills, _runner=_FakeRunner())
    # Assert
    assert "import mypkg" in result["quick_start"]


def test_run_asks_one_prompt_per_template_key(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    # Act
    run(skills, _runner=runner)
    # Assert
    assert len(runner.calls) == len(PYTHON_PACKAGE)


def test_run_passes_the_default_model_to_every_call(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    # Act
    run(skills, _runner=runner)
    # Assert
    assert all(call[1] == "claude-haiku-4-5" for call in runner.calls)


def test_run_per_prompt_above_one_returns_lists(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    # Act
    result = run(skills, runs_per_prompt=2, _runner=_FakeRunner())
    # Assert
    assert isinstance(result["what_for"], list)


def test_run_per_prompt_multiplies_call_count(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    # Act
    run(skills, runs_per_prompt=2, _runner=runner)
    # Assert
    assert len(runner.calls) == len(PYTHON_PACKAGE) * 2


def test_run_accepts_string_path(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    # Act
    result = run(str(skills), _runner=_FakeRunner())
    # Assert
    assert result["package"] == "mypkg"


def test_run_missing_dir_raises():
    # Arrange
    ctx = pytest.raises(FileNotFoundError)
    # Act
    # Assert
    with ctx:
        run("/nonexistent/path/__no__")


def test_run_empty_dir_raises(tmp_path):
    # Arrange
    empty = tmp_path / "empty"
    empty.mkdir()
    ctx = pytest.raises(FileNotFoundError)
    # Act
    # Assert
    with ctx:
        run(empty)


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_includes_heading(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    result = run(skills, _runner=_FakeRunner())
    # Act
    md = render_markdown(result)
    # Assert
    assert "## Skills Quality (verified by agent)" in md


def test_render_markdown_names_the_package(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    result = run(skills, _runner=_FakeRunner())
    # Act
    md = render_markdown(result)
    # Assert
    assert "Package: `mypkg`" in md


def test_render_markdown_ends_with_newline(tmp_path):
    # Arrange
    skills = _make_skills(tmp_path)
    result = run(skills, _runner=_FakeRunner())
    # Act
    md = render_markdown(result)
    # Assert
    assert md.endswith("\n")


# ---------------------------------------------------------------------------
# tests_newb.yaml / tests_newb.py author-tests discovery
# ---------------------------------------------------------------------------


def test_load_tests_missing_file_returns_empty(tmp_path):
    # Arrange
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs == []


def test_load_tests_parses_one_yaml_entry(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    (tmp_path / "tests_newb.yaml").write_text(
        "- name: pkg_purpose\n"
        "  prompt: What is this?\n"
        "  expect_contains: ['No', 'scitex-parallel']\n"
        "  expect_excludes: ['yes you can']\n"
    )
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs[0]["name"] == "pkg_purpose"


def test_load_tests_yaml_preserves_expect_contains(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    (tmp_path / "tests_newb.yaml").write_text(
        "- name: pkg_purpose\n"
        "  prompt: What is this?\n"
        "  expect_contains: ['scitex-parallel']\n"
    )
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert "scitex-parallel" in rs[0]["expect_contains"]


def test_load_tests_invalid_yaml_returns_empty(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    (tmp_path / "tests_newb.yaml").write_text("not: a list: just: garbage:")
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs == []


def test_load_tests_python_module_reads_named_entry(tmp_path):
    # Arrange
    (tmp_path / "tests_newb.py").write_text(
        "TESTS = [\n"
        '    {"name": "py_one", "prompt": "What does it do?",\n'
        '     "expect_contains": ["foo"]},\n'
        '    {"prompt": "Edge case?", "judge": "Must mention X"},\n'
        "]\n"
    )
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs[0]["name"] == "py_one"


def test_load_tests_python_module_auto_names_unnamed_entry(tmp_path):
    # Arrange
    (tmp_path / "tests_newb.py").write_text(
        "TESTS = [\n"
        '    {"name": "py_one", "prompt": "What does it do?"},\n'
        '    {"prompt": "Edge case?", "judge": "Must mention X"},\n'
        "]\n"
    )
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs[1]["name"] == "tests_newb_1"


def test_load_tests_concatenates_yaml_and_pytest_style_py(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    (tmp_path / "tests_newb.yaml").write_text("- name: yaml_one\n  prompt: From YAML\n")
    (tmp_path / "test_newb_extra.py").write_text(
        'TESTS = [{"name": "py_extra", "prompt": "From extra .py"}]\n'
    )
    # Act
    names = {r["name"] for r in _load_tests(tmp_path)}
    # Assert
    assert {"yaml_one", "py_extra"}.issubset(names)


def test_load_tests_python_without_TESTS_returns_empty(tmp_path):
    # Arrange
    (tmp_path / "tests_newb.py").write_text("# no TESTS defined\nx = 1\n")
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs == []


def test_load_tests_accepts_judge_field(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    (tmp_path / "tests_newb.yaml").write_text(
        "- name: redirect_check\n"
        "  prompt: How do I do parallel?\n"
        "  judge: Must say not supported and recommend an alternative.\n"
    )
    # Act
    rs = _load_tests(tmp_path)
    # Assert
    assert rs[0]["judge"].startswith("Must say")


# ---------------------------------------------------------------------------
# run() author-test grading
# ---------------------------------------------------------------------------


def test_run_with_author_tests_records_total(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: contains_check\n"
        "  prompt: Anything?\n"
        "  expect_contains: ['parallel']\n"
        "- name: judge_check\n"
        "  prompt: Anything else?\n"
        "  judge: Must say no parallel.\n"
    )
    # Act
    result = run(skills, _runner=_JudgeRunner())
    # Assert
    assert result["tests_summary"]["total"] == 2


def test_run_with_author_tests_records_passed(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: contains_check\n"
        "  prompt: Anything?\n"
        "  expect_contains: ['parallel']\n"
        "- name: judge_check\n"
        "  prompt: Anything else?\n"
        "  judge: Must say no parallel.\n"
    )
    # Act
    result = run(skills, _runner=_JudgeRunner())
    # Assert
    assert result["tests_summary"]["passed"] == 2


def test_run_judge_fail_lowers_passed_count(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: judge_check\n  prompt: Q\n  judge: criteria\n"
    )
    # Act
    result = run(skills, _runner=_JudgeRunner(verdict="FAIL: not enough detail"))
    # Assert
    assert result["tests_summary"]["passed"] == 0


def test_run_judge_fail_marks_test_not_passed(tmp_path):
    # Arrange
    pytest.importorskip("yaml")
    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: judge_check\n  prompt: Q\n  judge: criteria\n"
    )
    # Act
    result = run(skills, _runner=_JudgeRunner(verdict="FAIL: not enough detail"))
    # Assert
    assert result["tests"][0]["judge"]["passed"] is False


# ---------------------------------------------------------------------------
# _stage_skills_mount isolation
# ---------------------------------------------------------------------------


def test_stage_skills_mount_copies_target_file(tmp_path):
    # Arrange
    src = tmp_path / "src"
    src.mkdir()
    (src / "01_quick-start.md").write_text("# Quick Start\n")
    mount = _stage_skills_mount(src, "demo-pkg")
    try:
        # Act
        copied = mount / ".claude" / "skills" / "demo-pkg" / "01_quick-start.md"
        # Assert
        assert copied.is_file()
    finally:
        shutil.rmtree(mount, ignore_errors=True)


def test_stage_skills_mount_isolates_to_single_package(tmp_path):
    # Arrange
    src = tmp_path / "src"
    src.mkdir()
    (src / "01_quick-start.md").write_text("# Quick Start\n")
    mount = _stage_skills_mount(src, "demo-pkg")
    try:
        skills_root = mount / ".claude" / "skills"
        # Act
        names = sorted(p.name for p in skills_root.iterdir())
        # Assert
        assert names == ["demo-pkg"]
    finally:
        shutil.rmtree(mount, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero():
    # Arrange
    from click.testing import CliRunner

    from newb._cli import main

    # Act
    result = CliRunner().invoke(main, ["--help"])
    # Assert
    assert result.exit_code == 0


def test_cli_help_shows_example_block():
    # Arrange
    from click.testing import CliRunner

    from newb._cli import main

    # Act
    result = CliRunner().invoke(main, ["--help"])
    # Assert
    assert "Example" in result.output


def test_cli_help_documents_format_flag():
    # Arrange
    from click.testing import CliRunner

    from newb._cli import main

    # Act
    result = CliRunner().invoke(main, ["--help"])
    # Assert
    assert "--format" in result.output
