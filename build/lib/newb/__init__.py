"""newb — agentic testing for Python packages.

A fresh AI agent reads only your `_skills/` (or equivalent docs) and tries
to use your package. If it succeeds, your docs work. If it fails, your CI
tells you why.

Status: 0.0.1 placeholder release. Active development at
https://github.com/ywatanabe1989/newb.

Until the standalone implementation lands, the working prototype lives
inside scitex-dev:

    pip install scitex-dev[cli]
    scitex-dev skills self-explain <package>
"""
__version__ = "0.0.1"
