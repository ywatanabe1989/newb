"""Default template — the original 4 canonical newbie questions.

For any pip-installable Python project. The agent reads only the
package's docs (no host context, no tools beyond what the runner's
SDK options grant) and answers in this order:

  1. what_for         — ONE-sentence purpose
  2. problems_solved  — markdown table (3-5 rows)
  3. quick_start      — minimal code block
  4. when_not_to_use  — 1-2 sentences, or 'not specified in the skills'

Prompts interpolate ``{skills_path}`` — the absolute path inside the
staged container where the focused docs subdir lives.
"""

from __future__ import annotations

_PROMPT_WHAT_FOR = (
    "Use the Read tool to open every .md file under {skills_path} (there's "
    "exactly one package directory there). Then and answer in ONE sentence: "
    "what is this package for?"
)

_PROMPT_PROBLEMS = (
    "Use the Read tool to open every .md file under {skills_path} (there's "
    "exactly one package directory there). Then and list 3-5 problems this "
    "package solves. Output as a markdown table with columns: "
    "| # | Problem | Solution |. No prose around the table."
)

_PROMPT_QUICK_START = (
    "Use the Read tool to open every .md file under {skills_path} (there's "
    "exactly one package directory there). Then and show the minimal working "
    "example as a Python code block. Just the code, no commentary."
)

_PROMPT_WHEN_NOT_TO_USE = (
    "Use the Read tool to open every .md file under {skills_path} (there's "
    "exactly one package directory there). Then and answer in 1-2 sentences: "
    "when should someone NOT use this package? If the skills don't say, "
    "answer 'not specified in the skills'."
)

PROMPTS: dict[str, str] = {
    "what_for": _PROMPT_WHAT_FOR,
    "problems_solved": _PROMPT_PROBLEMS,
    "quick_start": _PROMPT_QUICK_START,
    "when_not_to_use": _PROMPT_WHEN_NOT_TO_USE,
}
