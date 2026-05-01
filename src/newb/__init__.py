"""newb — agentic testing for Python packages.

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

Aliases ``newb.verify`` and ``newb.self_explain`` are kept for
backward compat (removed in 1.0).
"""

from __future__ import annotations

import sys
import types

from ._verify import render_markdown, run, self_explain, verify

__version__ = "0.4.0"
__all__ = ["__version__", "render_markdown", "run", "self_explain", "verify"]


# Module-callable shortcut (PEP 562, Python 3.7+). Lets ``import newb;
# newb("./skills")`` work as a one-liner alias for ``newb.run``.
class _NewbModule(types.ModuleType):
    def __call__(self, skills_dir, **kwargs):  # type: ignore[no-untyped-def]
        return run(skills_dir, **kwargs)


sys.modules[__name__].__class__ = _NewbModule
