"""Read project-level newb config from ``pyproject.toml``.

Recognized section: ``[tool.newb]``. Currently supported keys:

- ``template`` — default question-template name
- ``runtime`` — default container runtime
- ``scope`` — default agent scope (``all`` | ``docs``)
- ``model`` — default Claude model id
- ``runs`` — default ``--runs`` value (int)
- ``install_mode`` — default install mode (``editable`` | ``wheel`` | ``pypi``)
- ``mcp_servers`` — table of MCP servers passed through to the
  in-container agent's ``ClaudeAgentOptions(mcp_servers=...)``.
  Validated host-side (see ``_mcp_validate``); JSON-encoded into
  ``NEWB_MCP_SERVERS_JSON`` for the container runner to consume.

Any unknown keys are ignored (forward-compat). CLI flags + env vars
take precedence over pyproject defaults; pyproject takes precedence
over hard-coded defaults.
"""

from __future__ import annotations

from pathlib import Path


def load_pyproject_config(start: Path | str) -> dict:
    """Walk up from ``start`` looking for ``pyproject.toml``; return
    its ``[tool.newb]`` table as a dict, or ``{}`` if absent / unreadable."""
    p = Path(start).resolve()
    if p.is_file():
        p = p.parent
    for d in (p, *p.parents):
        candidate = d / "pyproject.toml"
        if candidate.is_file():
            return _read_tool_newb(candidate)
    return {}


def _read_tool_newb(path: Path) -> dict:
    try:
        import tomllib  # py3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[import-not-found]
        except ImportError:
            return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except Exception:
        return {}
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return {}
    newb = tool.get("newb", {})
    return newb if isinstance(newb, dict) else {}


# Allowlist of keys the rest of newb knows how to consume. Unknown keys
# in [tool.newb] are silently ignored (forward-compat — future newb
# versions may add new keys; older versions shouldn't crash on them).
_RECOGNIZED_KEYS = {
    "template",
    "runtime",
    "scope",
    "model",
    "runs",
    "install_mode",
    "mcp_servers",
}


def merged_defaults(pyproject_dir: Path | str, **cli_overrides) -> dict:
    """Resolve effective defaults: CLI > pyproject > hard-coded.

    Returns a dict with only the keys present after resolution. ``None``
    in ``cli_overrides`` means "no flag passed"; pyproject value (if any)
    wins. Used by the CLI to layer flags onto project config.
    """
    project = {
        k: v
        for k, v in load_pyproject_config(pyproject_dir).items()
        if k in _RECOGNIZED_KEYS
    }
    out: dict = dict(project)
    for k, v in cli_overrides.items():
        if v is not None:
            out[k] = v
    return out
