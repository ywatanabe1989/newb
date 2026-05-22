#!/usr/bin/env python3
"""Inspect newb's question templates and public API — no agent run.

This example is offline: it touches neither Anthropic nor Docker. It
shows the surface you reason about *before* spending a verdict run:

  - the public Python API (`newb`, `newb.run`, `newb.render_markdown`)
  - the built-in question templates and the canonical question keys
  - the shape of the report dict a real run would return

Run::

    python examples/01_basic.py

Expected stdout is committed alongside as ``01_basic_out/stdout.txt``.
"""

from __future__ import annotations

import newb
from newb.question_templates import TEMPLATES, get_template


def main() -> int:
    # 1. Public API surface — what you import.
    print("newb version:", newb.__version__)
    print("callable    :", callable(newb))  # `newb(".")` is `newb.run(".")`
    print("public api  :", ", ".join(newb.__all__))
    print()

    # 2. Built-in templates — the prompt sets a run can pick from.
    print("templates   :", ", ".join(sorted(TEMPLATES)))
    print()

    # 3. The canonical question keys of the default template. A real
    #    `newb(".")` report has one top-level key per question id below,
    #    each carrying the agent's free-text answer.
    default = get_template("python-package")
    print("python-package question keys:")
    for key in default:
        print(f"  - {key}")
    print()

    # 4. The shape of a report — what `newb(".")` returns. (We print the
    #    schema, not a real run, so this example stays offline.)
    print("report dict shape (keys a real run fills in):")
    schema_keys = ["newb_signature", "package", "template", "runtime_info"]
    schema_keys += list(default)
    schema_keys += ["tests", "tests_summary"]  # present iff tests_newb.yaml
    for key in schema_keys:
        print(f"  {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
