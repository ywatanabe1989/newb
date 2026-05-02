"""Author-test loading + grading.

Extracted from ``_try.py`` for line-budget hygiene.

- ``_load_tests``: parse ``tests_newb.yaml`` into a normalized list.
- ``_judge``: ask the agent to PASS/FAIL an answer against criteria.
- ``_grade``: combine substring filters + LLM-judge into one verdict.
- ``_JUDGE_PROMPT``: the system prompt used by ``_judge``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def _normalize_entry(entry: dict, default_name: str) -> dict | None:
    """Coerce one raw test entry into the canonical shape, or ``None``
    if it lacks a prompt."""
    if not isinstance(entry, dict):
        return None
    prompt = entry.get("prompt")
    if not prompt:
        return None
    return {
        "name": str(entry.get("name") or default_name),
        "prompt": str(prompt),
        "expect_contains": list(entry.get("expect_contains") or []),
        "expect_excludes": list(entry.get("expect_excludes") or []),
        "judge": entry.get("judge"),
    }


def _load_yaml_tests(test_file: Path) -> list[dict]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return []
    try:
        data = yaml.safe_load(test_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for i, entry in enumerate(data):
        normalized = _normalize_entry(entry, f"test_{i}")
        if normalized is not None:
            out.append(normalized)
    return out


def _load_python_tests(test_file: Path) -> list[dict]:
    """Import a ``tests_newb.py`` / ``test_newb_*.py`` file and extract
    its module-level ``TESTS`` list.

    Each entry must be a dict with at minimum a ``prompt`` key.
    Optional: ``name``, ``expect_contains``, ``expect_excludes``, ``judge``.

    Example test file::

        # tests_newb.py
        TESTS = [
            {
                "name": "redirects_parallel",
                "prompt": "How do I run things in parallel?",
                "expect_contains": ["does not"],
                "judge": "Must redirect to an alternative tool.",
            },
        ]
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        f"_newb_user_tests_{test_file.stem}", test_file
    )
    if spec is None or spec.loader is None:
        return []
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return []
    raw = getattr(module, "TESTS", None)
    if not isinstance(raw, list):
        return []
    out = []
    for i, entry in enumerate(raw):
        normalized = _normalize_entry(entry, f"{test_file.stem}_{i}")
        if normalized is not None:
            out.append(normalized)
    return out


def _load_tests(skills_src: Path) -> list[dict]:
    """Load author tests, pytest-style discovery.

    Discovers, in order:

    1. ``tests_newb.yaml`` (canonical YAML form)
    2. ``tests_newb.py``  (Python module exporting ``TESTS = [...]``)
    3. ``test_newb_*.py`` (additional Python modules)

    All results are concatenated. Each entry must be a dict with at
    minimum a ``prompt`` key. Optional: ``name``, ``expect_contains``,
    ``expect_excludes``, ``judge``.
    """
    skills_src = Path(skills_src)
    out: list[dict] = []

    yaml_file = skills_src / "tests_newb.yaml"
    if yaml_file.is_file():
        out.extend(_load_yaml_tests(yaml_file))

    py_main = skills_src / "tests_newb.py"
    if py_main.is_file():
        out.extend(_load_python_tests(py_main))

    for py_file in sorted(skills_src.glob("test_newb_*.py")):
        out.extend(_load_python_tests(py_file))

    return out


_JUDGE_PROMPT = (
    "You are an objective test judge. The CRITERIA describes what a "
    "correct answer must include or do. The ANSWER is the candidate's "
    "response. Reply with exactly one line: 'PASS: <reason>' or "
    "'FAIL: <reason>'. Be strict.\n\n"
    "CRITERIA:\n{criteria}\n\nANSWER:\n{answer}"
)


def _judge(criteria: str, answer: str, runner, model: str) -> tuple[bool, str]:
    from ._try import _extract_text  # local: avoid import cycle

    res = runner.run(
        _JUDGE_PROMPT.format(criteria=criteria, answer=answer), model=model
    )
    text = _extract_text(res).strip()
    return text.upper().startswith("PASS"), text


def _grade(test: dict, answer: str, runner, model: str) -> dict:
    low = answer.lower()
    has_substring = bool(test["expect_contains"] or test["expect_excludes"])
    contains_ok = all(s.lower() in low for s in test["expect_contains"])
    excludes_ok = all(s.lower() not in low for s in test["expect_excludes"])
    substring_passed = contains_ok and excludes_ok
    out: Dict[str, Any] = {
        "name": test["name"],
        "prompt": test["prompt"],
        "answer": answer,
    }
    passed = True
    if has_substring:
        out["substring"] = {
            "contains_ok": contains_ok,
            "excludes_ok": excludes_ok,
            "passed": substring_passed,
        }
        passed = passed and substring_passed
    if test.get("judge"):
        j_passed, j_reason = _judge(test["judge"], answer, runner, model)
        out["judge"] = {"passed": j_passed, "reason": j_reason}
        passed = passed and j_passed
    if not (has_substring or test.get("judge")):
        passed = True
    out["passed"] = bool(passed)
    return out
