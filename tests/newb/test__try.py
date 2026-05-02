"""Tests for newb._try (docker / claude API are mocked)."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------


def test_module_imports_and_exports_callable():
    import newb

    assert callable(newb.render_markdown)
    assert callable(newb.test)
    # Module is callable as a shortcut for newb.test (PEP 562 trick).
    assert callable(newb)
    # `self_explain` was the deprecated alias — removed in 0.12.0.
    assert not hasattr(newb, "self_explain")
    assert "self_explain" not in newb.__all__
    # Version is resolved dynamically from importlib.metadata in
    # __init__.py, so just check the shape — not pin to a literal that
    # would drift with every release.
    assert isinstance(newb.__version__, str) and newb.__version__
    # Templates are now sourced from question_templates/<name>.py — _try.py
    # no longer re-exports _PROMPT_* aliases. Verify the canonical template
    # path instead.
    from newb.question_templates import PYTHON_PACKAGE

    assert isinstance(PYTHON_PACKAGE["what_for"], str)
    assert isinstance(PYTHON_PACKAGE["problems_solved"], str)
    assert isinstance(PYTHON_PACKAGE["quick_start"], str)
    assert isinstance(PYTHON_PACKAGE["when_not_to_use"], str)


# ---------------------------------------------------------------------------
# Mocked end-to-end
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


def test_run_returns_expected_keys(tmp_path):
    from newb import test

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    result = test(skills, _runner=runner)

    assert result["package"] == "mypkg"
    assert "what_for" in result
    assert "problems_solved" in result
    assert "quick_start" in result
    assert "when_not_to_use" in result
    assert "30+ formats" in result["what_for"]
    assert "| # | Problem | Solution |" in result["problems_solved"]
    assert "import mypkg" in result["quick_start"]
    # python-package template now has 6 prompts (added post_install_check
    # + prompt_injection_check that leverage the full-perms container).
    from newb.question_templates import PYTHON_PACKAGE

    assert len(runner.calls) == len(PYTHON_PACKAGE)
    assert all(call[1] == "claude-haiku-4-5" for call in runner.calls)


def test_run_runs_per_prompt_returns_lists(tmp_path):
    from newb import test

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    result = test(skills, runs_per_prompt=2, _runner=runner)

    assert isinstance(result["what_for"], list)
    assert len(result["what_for"]) == 2
    from newb.question_templates import PYTHON_PACKAGE

    assert len(runner.calls) == len(PYTHON_PACKAGE) * 2


def test_run_accepts_string_path(tmp_path):
    from newb import test

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    result = test(str(skills), _runner=runner)
    assert result["package"] == "mypkg"


def test_run_missing_dir_raises():
    from newb import test

    with pytest.raises(FileNotFoundError):
        test("/nonexistent/path/__no__")


def test_run_no_md_files_raises(tmp_path):
    from newb import test

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        test(empty)


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_shape(tmp_path):
    from newb import render_markdown, test

    skills = _make_skills(tmp_path)
    result = test(skills, _runner=_FakeRunner())
    md = render_markdown(result)

    assert "## Skills Quality (verified by agent)" in md
    assert "Package: `mypkg`" in md
    assert "**Q: What is this package for?**" in md
    assert "**Q: What problems does it solve?**" in md
    assert "**Q: How do I use it?**" in md
    assert "**Q: When should I NOT use this?**" in md
    assert md.endswith("\n")


# ---------------------------------------------------------------------------
# tests_newb.yaml (canonical author-tests format)
# ---------------------------------------------------------------------------


def test_load_tests_missing_file_returns_empty(tmp_path):
    from newb._try import _load_tests

    assert _load_tests(tmp_path) == []


def test_load_tests_parses_valid_yaml(tmp_path):
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text(
        "- name: pkg_purpose\n"
        "  prompt: What is this?\n"
        "  expect_contains: ['No', 'scitex-parallel']\n"
        "  expect_excludes: ['yes you can']\n"
    )
    rs = _load_tests(tmp_path)
    assert len(rs) == 1
    assert rs[0]["name"] == "pkg_purpose"
    assert rs[0]["prompt"] == "What is this?"
    assert "scitex-parallel" in rs[0]["expect_contains"]


def test_load_tests_invalid_yaml_returns_empty(tmp_path):
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text("not: a list: just: garbage:")
    assert _load_tests(tmp_path) == []


def test_load_tests_python_module(tmp_path):
    """tests_newb.py with TESTS list is discovered alongside YAML."""
    from newb._try import _load_tests

    (tmp_path / "tests_newb.py").write_text(
        "TESTS = [\n"
        '    {"name": "py_one", "prompt": "What does it do?",\n'
        '     "expect_contains": ["foo"]},\n'
        '    {"prompt": "Edge case?", "judge": "Must mention X"},\n'
        "]\n"
    )
    rs = _load_tests(tmp_path)
    assert len(rs) == 2
    assert rs[0]["name"] == "py_one"
    assert rs[0]["expect_contains"] == ["foo"]
    assert rs[1]["name"] == "tests_newb_1"  # auto-named
    assert rs[1]["judge"] == "Must mention X"


def test_load_tests_pytest_style_glob(tmp_path):
    """test_newb_*.py files are also picked up; YAML + .py concat."""
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text("- name: yaml_one\n  prompt: From YAML\n")
    (tmp_path / "test_newb_extra.py").write_text(
        'TESTS = [{"name": "py_extra", "prompt": "From extra .py"}]\n'
    )
    rs = _load_tests(tmp_path)
    names = {r["name"] for r in rs}
    assert "yaml_one" in names
    assert "py_extra" in names


def test_load_tests_python_missing_TESTS_returns_empty(tmp_path):
    """A test_newb_*.py without a TESTS list contributes zero entries."""
    from newb._try import _load_tests

    (tmp_path / "tests_newb.py").write_text("# no TESTS defined\nx = 1\n")
    assert _load_tests(tmp_path) == []


def test_load_tests_accepts_judge_field(tmp_path):
    pytest.importorskip("yaml")
    from newb._try import _load_tests

    (tmp_path / "tests_newb.yaml").write_text(
        "- name: redirect_check\n"
        "  prompt: How do I do parallel?\n"
        "  judge: Must say not supported and recommend an alternative.\n"
    )
    rs = _load_tests(tmp_path)
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


def test_run_with_yaml_tests_records_pass_fail(tmp_path):
    pytest.importorskip("yaml")
    from newb import test

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
    result = test(skills, _runner=runner)

    assert "tests" in result
    assert "tests_summary" in result
    assert result["tests_summary"]["total"] == 2
    assert result["tests_summary"]["passed"] == 2
    assert "red_tests" not in result  # back-compat alias removed in 0.12.0


def test_run_judge_fail_reflected_in_summary(tmp_path):
    pytest.importorskip("yaml")
    from newb import test

    skills = _make_skills(tmp_path)
    (skills / "tests_newb.yaml").write_text(
        "- name: judge_check\n  prompt: Q\n  judge: criteria\n"
    )
    runner = _JudgeRunner(verdict="FAIL: not enough detail")
    result = test(skills, _runner=runner)

    assert result["tests_summary"]["passed"] == 0
    assert result["tests"][0]["judge"]["passed"] is False


# ---------------------------------------------------------------------------
# _stage_skills_mount isolation
# ---------------------------------------------------------------------------


def test_stage_skills_mount_contains_only_target(tmp_path):
    import shutil

    from newb._try import _stage_skills_mount

    src = tmp_path / "src"
    src.mkdir()
    (src / "01_quick-start.md").write_text("# Quick Start\n")
    mount = _stage_skills_mount(src, "demo-pkg")
    try:
        copied = mount / ".claude" / "skills" / "demo-pkg"
        assert (copied / "01_quick-start.md").is_file()
        skills_root = mount / ".claude" / "skills"
        assert sorted(p.name for p in skills_root.iterdir()) == ["demo-pkg"]
        assert sorted(p.name for p in mount.iterdir()) == [".claude"]
    finally:
        shutil.rmtree(mount, ignore_errors=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_help_shows_example_block():
    from click.testing import CliRunner

    from newb._cli import main

    # pytest-style top-level: `newb <target>` is THE primary form.
    # All the canonical flags + the example block live on the group's
    # own --help (no subcommand needed for the try-action).
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Example" in result.output
    assert "newb ." in result.output  # canonical positional invocation
    assert "--format" in result.output
    assert "--template" in result.output
