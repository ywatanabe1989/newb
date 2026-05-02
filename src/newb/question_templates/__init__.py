"""Question templates — the prompt sets newb sends to the agent.

Each template is a `dict[str, str]` mapping a stable key (used in the
output JSON) to a prompt string. Prompts may interpolate
``{skills_path}`` (the absolute path inside the staged container
where the focused docs subdir lives).

Templates live as plain Python modules so they can grow assertions
or compute prompts dynamically; user-defined YAML overrides land in
a separate loader (see ``newb._try._load_tests``).

Built-in templates so far:

- ``python_package`` — the original 4 canonical questions: what for,
  problems solved, quick start, when not to use. Default for any
  pip-installable Python project.

Future ideas (not yet implemented): ``api_sdk``, ``cli_tool``,
``scientific``, ``web_app``, ``ml_model``. Add by dropping a new
module here that exposes a ``PROMPTS`` dict.
"""

from __future__ import annotations

from pathlib import Path

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
    """Look up a template by name. ``name`` may be:

    - A built-in template name (``python-package``, ``cli-tool``, …)
    - A path to a user-defined YAML file (``./my-template.yaml`` or
      ``/abs/path/to/template.yaml``)

    YAML format::

        name: my-template
        questions:
          - id: my_question
            prompt: "Read every .md and answer ..."
          - id: another
            prompt: "..."
    """
    # Built-in lookup
    if name in TEMPLATES:
        return TEMPLATES[name]
    # YAML file lookup
    p = Path(name).expanduser()
    if p.is_file() and p.suffix.lower() in {".yaml", ".yml"}:
        return load_yaml_template(p)
    raise KeyError(
        f"unknown template {name!r}; built-ins: {sorted(TEMPLATES)} "
        "(or pass a path to a .yaml file)"
    )


def load_yaml_template(path: Path) -> dict[str, str]:
    """Load a user-defined template from YAML. Requires the ``[yaml]`` extra."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as e:
        raise RuntimeError(
            "YAML templates require the [yaml] extra: `pip install newb[yaml]`"
        ) from e
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping at top level")
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError(f"{path}: expected `questions:` list")
    out: dict[str, str] = {}
    for i, entry in enumerate(questions):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: question[{i}] must be a mapping")
        qid = entry.get("id") or f"q_{i}"
        prompt = entry.get("prompt")
        if not isinstance(prompt, str):
            raise ValueError(f"{path}: question[{i}] missing string `prompt:`")
        out[str(qid)] = prompt
    if not out:
        raise ValueError(f"{path}: no questions defined")
    return out


__all__ = [
    "CLI_TOOL",
    "DEFAULT_TEMPLATE",
    "PYTHON_PACKAGE",
    "TEMPLATES",
    "get_template",
    "load_yaml_template",
]
