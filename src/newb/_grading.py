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


def _load_tests(skills_src: Path) -> list[dict]:
    """Load author tests from ``tests_newb.yaml``.

    Schema per entry::

        - name: optional human label
          prompt: "the question to ask the agent"
          expect_contains: [substrings that MUST appear]   # optional
          expect_excludes: [substrings that MUST NOT appear] # optional
          judge: "criteria text for an LLM judge"          # optional
    """
    test_file = Path(skills_src) / "tests_newb.yaml"
    if not test_file.is_file():
        return []
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
        if not isinstance(entry, dict):
            continue
        prompt = entry.get("prompt")
        if not prompt:
            continue
        out.append(
            {
                "name": str(entry.get("name") or f"test_{i}"),
                "prompt": str(prompt),
                "expect_contains": list(entry.get("expect_contains") or []),
                "expect_excludes": list(entry.get("expect_excludes") or []),
                "judge": entry.get("judge"),
            }
        )
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
