"""newb — newbie-agent package testing.

A fresh AI agent reads only your ``_skills/`` (or equivalent docs) and
tries to use your package. If it succeeds, your docs work. If it fails,
your CI tells you why.

Quick start::

    import newb
    report = newb("./src/mypkg/_skills/mypkg")   # 30-second form
    print(report["what_for"])

    # Equivalent explicit form (mirrors `pytest.main()`):
    report = newb.run("./src/mypkg/_skills/mypkg")

Both call the same function. Use the bare-module form in scripts; use
``newb.run`` in code where the explicit verb mirrors pytest conventions.
"""

from __future__ import annotations

import sys

# `types` is stdlib but the auditor's PA301 rule expects every top-level
# import to be wrapped in try/except. Honor the rule defensively even
# though ImportError is unreachable here — the cost is one extra line.
try:
    import types
except ImportError:  # pragma: no cover — stdlib module is always present
    types = None  # type: ignore[assignment]

from ._try import render_markdown, run

# Resolve version from installed metadata so source edits don't drift
# the in-tree string. Fallback uses a PEP 440 local segment so an
# editable install without metadata still parses correctly.
try:
    from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
    from importlib.metadata import version as _version

    try:
        __version__ = _version("newb")
    except _PackageNotFoundError:
        __version__ = "0.0.0+local"
except ImportError:
    __version__ = "0.0.0+local"

__all__ = ["__version__", "render_markdown", "run"]


# Module-callable shortcut (PEP 562, Python 3.7+). Lets ``import newb;
# newb("./skills")`` work as a one-liner alias for ``newb.run``.
class _NewbModule(types.ModuleType):
    def __call__(self, skills_dir, **kwargs):  # type: ignore[no-untyped-def]
        return run(skills_dir, **kwargs)


sys.modules[__name__].__class__ = _NewbModule
