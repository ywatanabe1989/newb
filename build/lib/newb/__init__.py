"""newb — agentic testing for Python packages.

A fresh AI agent reads only your `_skills/` (or equivalent docs) and tries
to use your package. If it succeeds, your docs work. If it fails, your CI
tells you why.
"""

__version__ = "0.1.0"

from ._verify import render_markdown, self_explain

__all__ = ["__version__", "render_markdown", "self_explain"]
