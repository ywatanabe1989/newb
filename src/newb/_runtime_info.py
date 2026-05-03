"""Pytest-style runtime-settings header for the verification report.

Renders to a ``runtime_info`` block in the JSON output and (via
``render_markdown`` in ``_try.py``) to a fenced YAML block at the top of
the markdown report. Goal: zero ambiguity about what the verification
agent saw — newb version, runtime, image, model, hardening flags, etc.
"""

from __future__ import annotations


def _build_runtime_info(
    *,
    runtime: str,
    runner,
    model: str,
    template: str,
    scope: str = "all",
    install_mode: str = "editable",
) -> dict:
    info: dict = {
        "newb_version": _newb_version(),
        "runtime": runtime,
        "model": model,
        "template": template,
        "scope": scope,
        "install_mode": install_mode,
    }
    image = getattr(runner, "image", None)
    if image:
        info["image"] = image
    skills_path = getattr(runner, "skills_path", None)
    if skills_path:
        info["skills_path"] = skills_path
    hardening = getattr(runner, "hardening", None)
    if hardening is not None:
        try:
            from ._hardening import hardening_summary

            info["hardening"] = hardening_summary(hardening)
        except Exception:
            info["hardening"] = "unavailable"
    info["setting_sources"] = []
    info["agent_resources"] = (
        "unconstrained"
        if hardening is None
        or (
            getattr(hardening, "memory", None) is None
            and getattr(hardening, "cpus", None) is None
            and getattr(hardening, "pids_limit", None) is None
        )
        else "capped"
    )
    return info


def _newb_version() -> str:
    try:
        from . import __version__ as _v

        return _v
    except Exception:
        return "unknown"


# Single source of truth for the project tagline. Referenced from
# `_build_signature()` so every report carries the same one-line
# framing, and from README.md (kept manually in sync — there's no
# build step that injects it).
NEWB_TAGLINE = (
    "Test your package through the eyes of a newbie agent — "
    "because that's who's reading your docs now."
)


def _build_signature() -> dict:
    """Return the self-describing signature embedded in every report.

    Tells readers (humans and tools) which version of newb produced
    this report, where to find the project, and what newb is for in
    one line. Surfaced both in the JSON envelope (top-level
    ``newb_signature``) and in the markdown render footer.
    """
    return {
        "tool": "newb",
        "version": _newb_version(),
        "tagline": NEWB_TAGLINE,
        "pypi": "https://pypi.org/project/newb/",
        "github": "https://github.com/ywatanabe1989/newb",
        "ecosystem": {
            "name": "SciTeX",
            "url": "https://scitex.ai",
        },
    }
