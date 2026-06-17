"""Sphinx configuration for the newb documentation build."""

from __future__ import annotations

import os
import sys
from importlib.metadata import PackageNotFoundError, version as _v

# Make the package importable for autodoc + sphinx-click.
sys.path.insert(0, os.path.abspath("../../src"))

project = "newb"
author = "Yusuke Watanabe"
copyright = "2026, Yusuke Watanabe"

try:
    release = _v("newb")
except PackageNotFoundError:
    release = "0.0.0+local"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_click",
]

# Heavy / optional deps the agent SDK pulls in — mocked so autodoc
# doesn't need them installed on the docs runner.
autodoc_mock_imports = [
    "claude_agent_sdk",
    "fastmcp",
    "transformers",
    "torch",
    "sentencepiece",
]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

# sphinx-click renders Click help verbatim; literal asterisks in help
# text (``*.git``, ``NEWB_*``, ``NN_*.md``) trip docutils' inline-emphasis
# detector. Suppress that specific category rather than mangling the CLI
# help strings.
suppress_warnings = ["docutils"]

html_theme = "sphinx_rtd_theme"
html_title = f"newb {release}"

html_context = {
    "display_github": True,
    "github_user": "ywatanabe1989",
    "github_repo": "newb",
    "github_version": "develop",
    "conf_py_path": "/docs/sphinx/",
}
