"""Question templates — the prompt sets newb sends to the agent.

Each template is a `dict[str, str]` mapping a stable key (used in the
output JSON) to a prompt string. Prompts may interpolate
``{skills_path}`` (the absolute path inside the staged container
where the focused docs subdir lives).

Templates live as plain Python modules so they can grow assertions
or compute prompts dynamically; user-defined YAML overrides land in
a separate loader (see ``newb._verify._load_tests``).

Built-in templates so far:

- ``python_package`` — the original 4 canonical questions: what for,
  problems solved, quick start, when not to use. Default for any
  pip-installable Python project.

Future ideas (not yet implemented): ``api_sdk``, ``cli_tool``,
``scientific``, ``web_app``, ``ml_model``. Add by dropping a new
module here that exposes a ``PROMPTS`` dict.
"""

from __future__ import annotations

from .cli_tool import PROMPTS as CLI_TOOL
from .python_package import PROMPTS as PYTHON_PACKAGE

# Registry — name → prompts mapping. ``--template`` on the CLI looks
# up by name; the bare-name keys map directly to the registered
# templates so users see e.g. ``--template python-package``.
TEMPLATES: dict[str, dict[str, str]] = {
    "python-package": PYTHON_PACKAGE,
    "cli-tool": CLI_TOOL,
}

DEFAULT_TEMPLATE = "python-package"


def get_template(name: str) -> dict[str, str]:
    """Look up a template by CLI-friendly name; raise on unknown."""
    if name not in TEMPLATES:
        raise KeyError(f"unknown template {name!r}; available: {sorted(TEMPLATES)}")
    return TEMPLATES[name]


__all__ = [
    "CLI_TOOL",
    "DEFAULT_TEMPLATE",
    "PYTHON_PACKAGE",
    "TEMPLATES",
    "get_template",
]
