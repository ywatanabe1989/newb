"""Have a fresh agent (mounted with only your skills/docs) self-explain it.

Decoupled from scitex-dev's ECOSYSTEM registry — public API takes a
``Path`` to a skills directory rather than an ecosystem distribution name.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Union

# ---------------------------------------------------------------------------
# Canonical prompts
# ---------------------------------------------------------------------------

_PROMPT_WHAT_FOR = (
    "Use the Read tool to open every .md file under /home/agent/.claude/skills/ (there's exactly one package directory there). Then and answer in ONE sentence: "
    "what is this package for?"
)

_PROMPT_PROBLEMS = (
    "Use the Read tool to open every .md file under /home/agent/.claude/skills/ (there's exactly one package directory there). Then and list 3-5 problems this "
    "package solves. Output as a markdown table with columns: "
    "| # | Problem | Solution |. No prose around the table."
)

_PROMPT_QUICK_START = (
    "Use the Read tool to open every .md file under /home/agent/.claude/skills/ (there's exactly one package directory there). Then and show the minimal working "
    "example as a Python code block. Just the code, no commentary."
)

_PROMPT_WHEN_NOT_TO_USE = (
    "Use the Read tool to open every .md file under /home/agent/.claude/skills/ (there's exactly one package directory there). Then and answer in 1-2 sentences: "
    "when should someone NOT use this package? If the skills don't say, "
    "answer 'not specified in the skills'."
)

_PROMPTS_DEFAULT = {
    "what_for": _PROMPT_WHAT_FOR,
    "problems_solved": _PROMPT_PROBLEMS,
    "quick_start": _PROMPT_QUICK_START,
    "when_not_to_use": _PROMPT_WHEN_NOT_TO_USE,
}

# Backward-compat alias.
_PROMPTS = _PROMPTS_DEFAULT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_red_tests(skills_src: Path) -> list[dict]:
    """Load per-package red tests from ``<skills_src>/_red_tests.yaml``."""
    red_file = Path(skills_src) / "_red_tests.yaml"
    if not red_file.is_file():
        return []
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return []
    try:
        data = yaml.safe_load(red_file.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for entry in data:
        if not isinstance(entry, dict) or "question" not in entry:
            continue
        out.append(
            {
                "question": str(entry["question"]),
                "expect_contains": list(entry.get("expect_contains") or []),
                "expect_excludes": list(entry.get("expect_excludes") or []),
            }
        )
    return out


def _stage_skills_mount(skills_src: Path, name: str) -> Path:
    """Build a temp dir shaped as ``<tmp>/.claude/skills/<name>/``."""
    tmp = Path(tempfile.mkdtemp(prefix=f"newb-self-explain-{name}-"))
    target = tmp / ".claude" / "skills" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skills_src, target)
    return tmp


def _validate_skills_dir(skills_dir: Path) -> Path:
    p = Path(skills_dir).expanduser().resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"skills_dir is not a directory: {p}")
    if not any(p.rglob("*.md")):
        raise FileNotFoundError(f"skills_dir contains no .md files: {p}")
    return p


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def self_explain(
    skills_dir: Union[Path, str],
    *,
    model: str = "claude-haiku-4-5",
    runs_per_prompt: int = 1,
    _runner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Have an agent (mounted with only the given skills) self-explain.

    Parameters
    ----------
    skills_dir
        Path to a directory containing ``.md`` skill files (and optionally
        a ``_red_tests.yaml``).
    model
        Claude model id passed to ``claude -p --model``.
    runs_per_prompt
        How many times to ask each prompt. >1 returns lists; ==1 returns
        scalars.
    _runner
        Test seam — inject a runner with a ``.run(prompt, model=...)``
        method to bypass docker.

    Returns
    -------
    dict
        ``{"package", "what_for", "problems_solved", "quick_start",
        "when_not_to_use"[, "red_tests"]}``.
    """
    skills_src = _validate_skills_dir(Path(skills_dir))
    name = skills_src.name

    runner = _runner
    cleanup_mount: Optional[Path] = None
    try:
        if runner is None:
            from ._runner import NewbieDockerRunner

            mount = _stage_skills_mount(skills_src, name)
            cleanup_mount = mount
            runner = NewbieDockerRunner(skills_mount=mount)

        out: Dict[str, Any] = {"package": name}
        for key, prompt in _PROMPTS.items():
            answers = []
            for _ in range(max(1, int(runs_per_prompt))):
                result = runner.run(prompt, model=model)
                answers.append(_extract_text(result))
            out[key] = answers[0] if runs_per_prompt == 1 else answers

        red_results = []
        for entry in _load_red_tests(skills_src):
            ans_text = _extract_text(runner.run(entry["question"], model=model))
            low = ans_text.lower()
            passes_contains = all(s.lower() in low for s in entry["expect_contains"])
            passes_excludes = all(
                s.lower() not in low for s in entry["expect_excludes"]
            )
            red_results.append(
                {
                    "question": entry["question"],
                    "answer": ans_text,
                    "passed": bool(passes_contains and passes_excludes),
                }
            )
        if red_results:
            out["red_tests"] = red_results
        return out
    finally:
        if cleanup_mount is not None and cleanup_mount.exists():
            shutil.rmtree(cleanup_mount, ignore_errors=True)
        if runner is not None and hasattr(runner, "close") and _runner is None:
            try:
                runner.close()
            except Exception:
                pass


def _extract_text(result: Any) -> str:
    """Pull the assistant's final text from a ``claude -p`` JSON envelope."""
    if isinstance(result, dict):
        r = result.get("result")
        if isinstance(r, str):
            return r
    if isinstance(result, str):
        return result
    return ""


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_markdown(payload: Dict[str, Any]) -> str:
    """Render ``self_explain`` output as a README-ready markdown block."""
    import datetime

    pkg = payload.get("package", "<package>")
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    parts: list[str] = [
        "## Skills Quality (verified by agent)",
        "",
        "> Generated by a fresh agent reading only this package's `_skills/` directory.",
        f"> Package: `{pkg}`. Last verified: {today} (UTC).",
        "",
    ]

    def _block(value: Any) -> str:
        if isinstance(value, list):
            return "\n\n---\n\n".join(str(v) for v in value)
        return str(value)

    if "what_for" in payload:
        parts += [
            "**Q: What is this package for?**",
            "",
            "> " + _block(payload["what_for"]).replace("\n", "\n> "),
            "",
        ]
    if "problems_solved" in payload:
        parts += [
            "**Q: What problems does it solve?**",
            "",
            _block(payload["problems_solved"]).strip(),
            "",
        ]
    if "quick_start" in payload:
        parts += [
            "**Q: How do I use it?**",
            "",
            _block(payload["quick_start"]).strip(),
            "",
        ]
    if "when_not_to_use" in payload:
        parts += [
            "**Q: When should I NOT use this?**",
            "",
            "> " + _block(payload["when_not_to_use"]).replace("\n", "\n> "),
            "",
        ]
    red = payload.get("red_tests") or []
    if red:
        parts += ["### Boundary tests", ""]
        for entry in red:
            mark = "PASS" if entry.get("passed") else "FAIL"
            parts += [
                f"- **Q:** {entry['question']}",
                f"  - **A:** {entry['answer'].strip()} [{mark}]",
            ]
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


# EOF
