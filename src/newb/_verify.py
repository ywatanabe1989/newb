"""Have a fresh agent (mounted with only your skills/docs) self-explain it.

Decoupled from scitex-dev's ECOSYSTEM registry — public API takes a
``Path`` to a skills directory rather than an ecosystem distribution name.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Canonical prompts
# ---------------------------------------------------------------------------

_PROMPT_WHAT_FOR = (
    "Use the Read tool to open every .md file under {skills_path} (there's exactly one package directory there). Then and answer in ONE sentence: "
    "what is this package for?"
)

_PROMPT_PROBLEMS = (
    "Use the Read tool to open every .md file under {skills_path} (there's exactly one package directory there). Then and list 3-5 problems this "
    "package solves. Output as a markdown table with columns: "
    "| # | Problem | Solution |. No prose around the table."
)

_PROMPT_QUICK_START = (
    "Use the Read tool to open every .md file under {skills_path} (there's exactly one package directory there). Then and show the minimal working "
    "example as a Python code block. Just the code, no commentary."
)

_PROMPT_WHEN_NOT_TO_USE = (
    "Use the Read tool to open every .md file under {skills_path} (there's exactly one package directory there). Then and answer in 1-2 sentences: "
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
    """Back-compat shim — see ``_load_tests``."""
    return _load_tests(skills_src)


def _load_tests(skills_src: Path) -> list[dict]:
    """Load author tests from ``tests_newb.yaml`` (or legacy ``_red_tests.yaml``).

    Schema per entry::

        - name: optional human label
          prompt: "the question to ask the agent"
          expect_contains: [substrings that MUST appear]   # optional
          expect_excludes: [substrings that MUST NOT appear] # optional
          judge: "criteria text for an LLM judge"          # optional

    The legacy ``question`` key is accepted as an alias for ``prompt``.
    """
    candidates = [
        Path(skills_src) / "tests_newb.yaml",
        Path(skills_src) / "_red_tests.yaml",
    ]
    test_file = next((p for p in candidates if p.is_file()), None)
    if test_file is None:
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
        prompt = entry.get("prompt") or entry.get("question")
        if not prompt:
            continue
        out.append(
            {
                "name": str(entry.get("name") or f"test_{i}"),
                "prompt": str(prompt),
                "question": str(prompt),  # back-compat alias
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
        "question": test["prompt"],  # back-compat
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


def _stage_skills_mount(skills_src: Path, name: str) -> Path:
    """Build a temp dir shaped as ``<tmp>/.claude/skills/<name>/``."""
    tmp = Path(tempfile.mkdtemp(prefix=f"newb-self-explain-{name}-"))
    target = tmp / ".claude" / "skills" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skills_src, target)
    return tmp


_PROJECT_ROOT_MARKERS = (
    ".git",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "Cargo.toml",
    "go.mod",
)


def _find_project_root(start: Path) -> Optional[Path]:
    """Walk up from ``start`` looking for a project-root marker.

    Returns the first ancestor (or ``start`` itself) that contains any
    of ``.git``, ``pyproject.toml``, ``setup.py``, ``package.json``,
    ``Cargo.toml``, or ``go.mod``. If nothing is found before reaching
    the filesystem root, returns ``None`` (caller falls back to
    ``start``).
    """
    p = start if start.is_dir() else start.parent
    while True:
        if any((p / m).exists() for m in _PROJECT_ROOT_MARKERS):
            return p
        if p.parent == p:
            return None
        p = p.parent


def _validate_skills_dir(skills_dir: Path) -> Path:
    """Sanity-check the docs/skills source.

    Must be a directory containing at least one .md file (recursive).
    The .md guard is a smoke-test, not a format restriction — the agent
    will see every file in the eventual cwd via the Read tool.
    """
    p = Path(skills_dir).expanduser().resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"docs source is not a directory: {p}")
    if not any(p.rglob("*.md")):
        raise FileNotFoundError(f"docs source contains no .md files: {p}")
    return p


def _is_url(spec: Any) -> bool:
    return isinstance(spec, str) and (
        spec.startswith(("http://", "https://", "git@")) or spec.endswith(".git")
    )


def _resolve_source(spec: Union[Path, str]) -> Tuple[Path, Optional[Path]]:
    """Resolve a source spec to a local docs/skills directory.

    Returns ``(docs_dir, cleanup_dir_or_None)``. The cleanup dir (the
    parent of a git clone) is the caller's responsibility to ``rmtree``.

    Local paths pass through. Git URLs (``http(s)://``, ``git@``, or
    ``*.git``) are shallow-cloned to a temp dir; we then prefer
    ``_skills/``, then ``docs/``, then the repo root.
    """
    if not _is_url(spec):
        return Path(spec).expanduser().resolve(), None
    tmp = Path(tempfile.mkdtemp(prefix="newb-clone-"))
    repo = tmp / "repo"
    proc = subprocess.run(
        ["git", "clone", "--depth=1", str(spec), str(repo)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(
            f"git clone failed for {spec!r}: {proc.stderr[:300] or proc.stdout[:300]}"
        )
    for cand in [repo / "_skills", repo / "docs", repo]:
        if cand.is_dir() and any(cand.rglob("*.md")):
            return cand, tmp
    shutil.rmtree(tmp, ignore_errors=True)
    raise FileNotFoundError(f"No .md files found in cloned repo: {spec}")


def _make_runner(
    *,
    skills_dir: Path,
    project_root: Path,
    model: str,
    runtime: str = "docker",
) -> Any:
    """Build a runner.

    ``project_root`` is what the agent will see as cwd — the package's
    install location (auto-detected from ``.git`` / ``pyproject.toml``
    / ``setup.py`` markers). ``skills_dir`` is the focused docs/skills
    subdir the prompts point at via the ``{skills_path}`` placeholder.

    ``runtime`` selects the container isolation backend:

    * ``docker`` (default) — run the SDK inside
      ``ghcr.io/ywatanabe1989/newb-runner``; hard isolation (only the
      staged project root is bind-mounted ro). ~15-20s/q after image
      pull. The agent gets full agentic permissions inside (Read +
      Write + Edit + Bash + Glob + Grep) — container is the boundary,
      not the SDK options.
    * ``apptainer`` — same image via ``apptainer run docker://...``;
      HPC use case where docker isn't allowed.

    The ``host`` runtime was removed in newb 0.9 — full agent
    permissions on the host are unsafe (agent could ``rm -rf`` the
    user's projects, ``pip install`` into the global env, …) and
    "container is the boundary" only holds when there IS a container.
    """
    if runtime == "docker":
        from ._container_runner import DockerRunner

        return DockerRunner(
            skills_mount=skills_dir, project_root=project_root, model=model
        )
    if runtime == "apptainer":
        from ._container_runner import ApptainerRunner

        return ApptainerRunner(
            skills_mount=skills_dir, project_root=project_root, model=model
        )
    raise ValueError(
        f"unknown runtime: {runtime!r} (expected docker / apptainer; "
        "host removed in newb 0.9 — see CHANGELOG)"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(
    skills_dir: Union[Path, str],
    *,
    model: str = "claude-haiku-4-5",
    runs_per_prompt: int = 1,
    runtime: str = "host",
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
    if _runner is None:
        resolved, cleanup_clone = _resolve_source(skills_dir)
    else:
        resolved, cleanup_clone = Path(skills_dir), None
    skills_src = _validate_skills_dir(resolved)
    name = skills_src.name

    # The agent's cwd should be the package's install location — the
    # full project context (README, src/, tests/, _skills/, examples/),
    # not just the focused docs subdir. Auto-detect via .git/pyproject
    # markers; fall back to the docs dir itself if nothing found.
    project_root = _find_project_root(skills_src) or skills_src

    runner = _runner
    cleanup_mount: Optional[Path] = None
    try:
        if runner is None:
            runner = _make_runner(
                skills_dir=skills_src,
                project_root=project_root,
                model=model,
                runtime=runtime,
            )

        # Resolve the skills path the agent will see inside the runner.
        # Docker mounts at /home/agent/.claude/skills/; LocalRunner uses
        # an isolated HOME. Each runner can expose `.skills_path` to
        # override the default. The path is interpolated into prompts so
        # the agent reads from the right place.
        skills_path = getattr(runner, "skills_path", "/home/agent/.claude/skills/")

        out: Dict[str, Any] = {"package": name}
        for key, prompt in _PROMPTS.items():
            answers = []
            rendered = prompt.format(skills_path=skills_path)
            for _ in range(max(1, int(runs_per_prompt))):
                result = runner.run(rendered, model=model)
                answers.append(_extract_text(result))
            out[key] = answers[0] if runs_per_prompt == 1 else answers

        test_results = []
        for entry in _load_tests(skills_src):
            ans_text = _extract_text(runner.run(entry["prompt"], model=model))
            test_results.append(_grade(entry, ans_text, runner, model))
        if test_results:
            passed = sum(1 for t in test_results if t["passed"])
            out["tests"] = test_results
            out["tests_summary"] = {
                "passed": passed,
                "total": len(test_results),
            }
            out["red_tests"] = test_results  # back-compat
        return out
    finally:
        if cleanup_mount is not None and cleanup_mount.exists():
            shutil.rmtree(cleanup_mount, ignore_errors=True)
        if cleanup_clone is not None and cleanup_clone.exists():
            shutil.rmtree(cleanup_clone, ignore_errors=True)
        if runner is not None and hasattr(runner, "close") and _runner is None:
            try:
                runner.close()
            except Exception:
                pass


# Backward-compat alias. Removed in 1.0.
self_explain = run


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
