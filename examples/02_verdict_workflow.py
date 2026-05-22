#!/usr/bin/env python3
"""The doc-quality verdict workflow — definition file -> graded verdict.

This is the heart of correct `newb` usage. A `tests_newb.yaml` next to a
package's docs declares EXTRA questions with author-defined grading
(substring filters + optional LLM judge). `newb <docs-dir>` then:

  1. spins a fresh agent in a container,
  2. points it at the package,
  3. asks the canonical template questions + every tests_newb.yaml entry,
  4. grades each entry (expect_contains AND expect_excludes AND judge),
  5. emits a JSON report with a ``tests[]`` array + ``tests_summary``.

To keep this example offline (no Anthropic / Docker spend) it does NOT
launch an agent. Instead it:

  - parses the committed ``tests_newb.yaml`` with newb's OWN loader
    (``newb._grading._load_tests``) — the real code path,
  - documents the exact CLI command you would run,
  - prints the JSON verdict such a run produces.

To actually run the verdict (consumes Anthropic quota, needs Docker)::

    export NEWB_ANTHROPIC_API_KEY=sk-ant-...
    newb examples/02_verdict_workflow_sample/_skills/greetlib --json

Expected stdout is committed alongside as ``02_verdict_workflow_out/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from newb._grading import _load_tests

_HERE = Path(__file__).resolve().parent
_SKILLS = _HERE / "02_verdict_workflow_sample" / "_skills" / "greetlib"


def main() -> int:
    # 1. The definition file newb discovers. It lives NEXT TO the docs.
    yaml_path = _SKILLS / "tests_newb.yaml"
    print("definition file :", yaml_path.relative_to(_HERE))
    print()

    # 2. Parse it with newb's own loader — the real parsing path. This
    #    normalizes each entry to {name, prompt, expect_contains,
    #    expect_excludes, judge}.
    entries = _load_tests(_SKILLS)
    print(f"parsed {len(entries)} author test(s):")
    for e in entries:
        print(f"  - {e['name']}")
        print(f"      expect_contains : {e['expect_contains']}")
        print(f"      expect_excludes : {e['expect_excludes']}")
        print(f"      judge           : {bool(e['judge'])}")
    print()

    # 3. The exact CLI command. NOTE: `newb <dir>` is verb-less
    #    (pytest-style) — the docs dir is the positional, no subcommand.
    cmd = "newb examples/02_verdict_workflow_sample/_skills/greetlib --json"
    print("run with        :")
    print(f"  $ {cmd}")
    print()

    # 4. The JSON verdict such a run produces. The canonical template
    #    keys carry the agent's free-text; tests[] carries graded
    #    author-test verdicts; tests_summary aggregates pass/total.
    expected_verdict = {
        "package": "greetlib",
        "template": "python-package",
        "post_install_check_parsed": {
            "install": "ok",
            "import": "ok",
            "cli": "n/a",
        },
        "prompt_injection_check_parsed": {"verdict": "no", "evidence": ""},
        "tests": [
            {
                "name": "quick_start_imports_greet",
                "substring": {
                    "contains_ok": True,
                    "excludes_ok": True,
                    "passed": True,
                },
                "passed": True,
            },
            {
                "name": "redirects_parallel",
                "substring": {
                    "contains_ok": True,
                    "excludes_ok": True,
                    "passed": True,
                },
                "judge": {
                    "passed": True,
                    "reason": "PASS: redirects, no flag invented",
                },
                "passed": True,
            },
        ],
        "tests_summary": {"passed": 2, "total": 2},
    }
    print("expected verdict (jq-able for CI gating):")
    print(json.dumps(expected_verdict, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
