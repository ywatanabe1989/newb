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

# Prompt sets live in ``question_templates/`` so new templates
# (api_sdk, cli_tool, scientific, …) can land alongside the
# python_package default without touching this file.
from .question_templates import get_template


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Grading helpers extracted to ._grading; runtime-info to ._runtime_info.
from ._grading import _grade, _judge, _JUDGE_PROMPT, _load_tests  # noqa: F401, E402
from ._runtime_info import _build_runtime_info, _build_signature, _newb_version  # noqa: F401, E402


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


def _validate_source(source_dir: Path) -> Path:
    """Sanity-check the source directory.

    Must be a directory and non-empty. Any file type is acceptable —
    README, .py, .ipynb, .pdf, .yaml, scratch notes, anything. The
    agent's Read tool sees every file inside the staged cwd; newb
    doesn't filter by extension. (Earlier versions required at least
    one .md file as a smoke test; lifted in 0.10 — pip-installable
    packages without ANY .md still benefit from a try-run.)
    """
    p = Path(source_dir).expanduser().resolve()
    if not p.is_dir():
        raise FileNotFoundError(f"source is not a directory: {p}")
    if not any(p.iterdir()):
        raise FileNotFoundError(f"source directory is empty: {p}")
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
    # No .md filter — clone-root always wins. The agent decides what
    # to read once cwd is the staged project root.
    if repo.is_dir() and any(repo.iterdir()):
        return repo, tmp
    shutil.rmtree(tmp, ignore_errors=True)
    raise FileNotFoundError(f"cloned repo is empty: {spec}")


def _make_runner(
    *,
    skills_dir: Path,
    project_root: Path,
    model: str,
    runtime: str = "docker",
    hardening=None,
    scope: str = "all",
    mcp_servers: Optional[Dict[str, Any]] = None,
    pip_cache_dir: Optional[str] = None,
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
            skills_mount=skills_dir,
            project_root=project_root,
            model=model,
            hardening=hardening,
            scope=scope,
            mcp_servers=mcp_servers,
            pip_cache_dir=pip_cache_dir,
        )
    if runtime == "podman":
        from ._container_runner import PodmanRunner

        return PodmanRunner(
            skills_mount=skills_dir,
            project_root=project_root,
            model=model,
            hardening=hardening,
            scope=scope,
            mcp_servers=mcp_servers,
            pip_cache_dir=pip_cache_dir,
        )
    if runtime == "apptainer":
        from ._container_runner import ApptainerRunner

        return ApptainerRunner(
            skills_mount=skills_dir,
            project_root=project_root,
            model=model,
            scope=scope,
            mcp_servers=mcp_servers,
            pip_cache_dir=pip_cache_dir,
        )
    raise ValueError(
        f"unknown runtime: {runtime!r} (expected docker / podman / apptainer; "
        "host removed in newb 0.9 — see CHANGELOG)"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_INSTALL_MODE_CMD = {
    "editable": "pip install -e .",
    "wheel": "pip wheel --no-deps -w /tmp/newb-wheel . && pip install /tmp/newb-wheel/*.whl",
    "pypi": "pip install $(grep -oP '(?<=^name = \")[^\"]+' pyproject.toml | head -1)",
}


def run(
    skills_dir: Union[Path, str],
    *,
    model: str = "claude-haiku-4-5",
    runs_per_prompt: int = 1,
    runtime: str = "docker",
    template: str = "python-package",
    hardening=None,
    scope: str = "all",
    install_mode: str = "editable",
    mcp_servers: Optional[Dict[str, Any]] = None,
    pip_cache_dir: Optional[str] = None,
    verbosity: int = 0,
    _runner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Have an agent (mounted with only the given skills) self-explain.

    Parameters
    ----------
    skills_dir
        Path to a directory containing ``.md`` skill files (and optionally
        a ``tests_newb.yaml``).
    model
        Claude model id passed to the SDK.
    runs_per_prompt
        How many times to ask each prompt. >1 returns lists; ==1 returns
        scalars.
    runtime
        Container backend: ``docker`` (default) or ``apptainer``.
    template
        Question-template name from ``newb.question_templates`` (default
        ``python-package``).
    _runner
        Test seam — inject a runner with a ``.run(prompt, model=...)``
        method to bypass docker.

    Returns
    -------
    dict
        ``{"package", <prompt-keys-from-the-template>...
        [, "tests", "tests_summary"]}``.
    """
    prompts = get_template(template)
    if _runner is None:
        resolved, cleanup_clone = _resolve_source(skills_dir)
    else:
        resolved, cleanup_clone = Path(skills_dir), None
    skills_src = _validate_source(resolved)
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
                hardening=hardening,
                scope=scope,
                mcp_servers=mcp_servers,
                pip_cache_dir=pip_cache_dir,
            )

        # Resolve the skills path the agent will see inside the runner.
        # Docker mounts at /home/agent/.claude/skills/; LocalRunner uses
        # an isolated HOME. Each runner can expose `.skills_path` to
        # override the default. The path is interpolated into prompts so
        # the agent reads from the right place.
        skills_path = getattr(runner, "skills_path", "/home/agent/.claude/skills/")

        out: Dict[str, Any] = {
            "newb_signature": _build_signature(),
            "package": name,
            "template": template,
            "runtime_info": _build_runtime_info(
                runtime=runtime,
                runner=runner,
                model=model,
                template=template,
                scope=scope,
                install_mode=install_mode,
            ),
        }
        install_cmd = _INSTALL_MODE_CMD.get(install_mode, _INSTALL_MODE_CMD["editable"])
        # Build a single batch covering every (key, run-index) pair so
        # the entire template runs in ONE container invocation. The
        # in-container runner shares /work/project's filesystem state
        # across prompts (so `pip install -e .` from post_install_check
        # carries forward) but uses an independent ``query()`` per
        # prompt so conversation context never leaks between answers.
        batch_keys: list[tuple[str, int]] = []
        batch_prompts: list[str] = []
        for key, prompt in prompts.items():
            rendered = prompt.format(
                skills_path=skills_path,
                install_cmd=install_cmd,
            )
            for run_idx in range(max(1, int(runs_per_prompt))):
                batch_keys.append((key, run_idx))
                batch_prompts.append(rendered)
        run_batch = getattr(runner, "run_batch", None)
        if callable(run_batch):
            try:
                batch_results = run_batch(
                    batch_prompts, model=model, verbosity=verbosity
                )
            except TypeError:
                # Older runner shims without `verbosity` kwarg.
                batch_results = run_batch(batch_prompts, model=model)
        else:
            # Test-seam runners that only implement .run(prompt) — fall
            # back to per-prompt calls. Real container runners always
            # implement run_batch (single docker startup).
            batch_results = [runner.run(p, model=model) for p in batch_prompts]
        per_key: Dict[str, list] = {}
        for (key, _), result in zip(batch_keys, batch_results):
            per_key.setdefault(key, []).append(_extract_text(result))
        for key, answers in per_key.items():
            out[key] = answers[0] if runs_per_prompt == 1 else answers

        # Attach structured `<key>_parsed` siblings so CI can gate
        # on clean values instead of grepping free-text replies.
        from ._parsers import attach_parsed_fields

        attach_parsed_fields(out)

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


def _extract_text(result: Any) -> str:
    """Pull the assistant's final text from a ``claude -p`` JSON envelope."""
    if isinstance(result, dict):
        r = result.get("result")
        if isinstance(r, str):
            return r
    if isinstance(result, str):
        return result
    return ""


# Markdown rendering lives in ``_render.py`` (line-budget hygiene).
# Re-exported here so existing call sites (``newb._try.render_markdown``)
# keep working.
from ._render import render_markdown  # noqa: F401, E402


# EOF
