"""Tests for newb._verify (docker / claude API are mocked)."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------


def test_module_imports_and_exports_callable():
    import newb
    from newb import _verify

    assert callable(newb.self_explain)
    assert callable(newb.render_markdown)
    assert callable(newb.verify)
    # Module is callable as a shortcut for newb.verify (PEP 562 trick).
    assert callable(newb)
    # Backward-compat: self_explain is now an alias for verify.
    assert newb.self_explain is newb.verify
    assert newb.__version__ == "0.2.0"
    assert isinstance(_verify._PROMPT_WHAT_FOR, str)
    assert isinstance(_verify._PROMPT_PROBLEMS, str)
    assert isinstance(_verify._PROMPT_QUICK_START, str)
    assert isinstance(_verify._PROMPT_WHEN_NOT_TO_USE, str)


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


def test_self_explain_returns_expected_keys(tmp_path):
    from newb import self_explain

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    result = self_explain(skills, _runner=runner)

    assert result["package"] == "mypkg"
    assert "what_for" in result
    assert "problems_solved" in result
    assert "quick_start" in result
    assert "when_not_to_use" in result
    assert "30+ formats" in result["what_for"]
    assert "| # | Problem | Solution |" in result["problems_solved"]
    assert "import mypkg" in result["quick_start"]
    assert len(runner.calls) == 4
    assert all(call[1] == "claude-haiku-4-5" for call in runner.calls)


def test_self_explain_runs_per_prompt_returns_lists(tmp_path):
    from newb import self_explain

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    result = self_explain(skills, runs_per_prompt=2, _runner=runner)

    assert isinstance(result["what_for"], list)
    assert len(result["what_for"]) == 2
    assert len(runner.calls) == 8


def test_self_explain_accepts_string_path(tmp_path):
    from newb import self_explain

    skills = _make_skills(tmp_path)
    runner = _FakeRunner()
    result = self_explain(str(skills), _runner=runner)
    assert result["package"] == "mypkg"


def test_self_explain_missing_dir_raises():
    from newb import self_explain

    with pytest.raises(FileNotFoundError):
        self_explain("/nonexistent/path/__no__")


def test_self_explain_no_md_files_raises(tmp_path):
    from newb import self_explain

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        self_explain(empty)


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_shape(tmp_path):
    from newb import render_markdown, self_explain

    skills = _make_skills(tmp_path)
    result = self_explain(skills, _runner=_FakeRunner())
    md = render_markdown(result)

    assert "## Skills Quality (verified by agent)" in md
    assert "Package: `mypkg`" in md
    assert "**Q: What is this package for?**" in md
    assert "**Q: What problems does it solve?**" in md
    assert "**Q: How do I use it?**" in md
    assert "**Q: When should I NOT use this?**" in md
    assert md.endswith("\n")


# ---------------------------------------------------------------------------
# _load_red_tests
# ---------------------------------------------------------------------------


def test_load_red_tests_missing_file_returns_empty(tmp_path):
    from newb._verify import _load_red_tests

    assert _load_red_tests(tmp_path) == []


def test_load_red_tests_parses_valid_yaml(tmp_path):
    pytest.importorskip("yaml")
    from newb._verify import _load_red_tests

    (tmp_path / "_red_tests.yaml").write_text(
        "- question: Can this do parallel execution?\n"
        "  expect_contains: ['No', 'scitex-parallel']\n"
        "  expect_excludes: ['yes you can']\n"
    )
    rs = _load_red_tests(tmp_path)
    assert len(rs) == 1
    assert rs[0]["question"].startswith("Can this do parallel")
    assert "scitex-parallel" in rs[0]["expect_contains"]


def test_load_red_tests_invalid_yaml_returns_empty(tmp_path):
    pytest.importorskip("yaml")
    from newb._verify import _load_red_tests

    (tmp_path / "_red_tests.yaml").write_text("not: a list: just: garbage:")
    assert _load_red_tests(tmp_path) == []


# ---------------------------------------------------------------------------
# _stage_skills_mount isolation
# ---------------------------------------------------------------------------


def test_stage_skills_mount_contains_only_target(tmp_path):
    import shutil

    from newb._verify import _stage_skills_mount

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

    result = CliRunner().invoke(main, ["verify", "--help"])
    assert result.exit_code == 0
    assert "Example" in result.output
    assert "newb verify" in result.output
    assert "--json" in result.output
    assert "--format" in result.output
