---
description: |
  [TOPIC] Ci Integration
  [DETAILS] Wire newb into CI — JSON output for parsing, markdown for README updates, exit-code semantics, the `<key>_parsed` structured fields, the `newb gate` declarative criteria evaluator, and a sample GitHub Actions step.
tags: [newb-ci-integration]
---

# CI integration

newb is designed to be one shell line in a CI step. The CLI's two
output formats (`json` for machines, `markdown` for paste-into-README)
cover both common needs.

## Exit codes

`newb <target>` exits **0** as long as the SDK call completed and
produced a report. Test failures (`expect_contains` / `judge`
returning `false`) and structured-question failures (`INSTALL: fail`)
do **not** fail the process — they appear in the report.

For hard-gating, run `newb gate <report.json>` after the run; that
exits 1 when criteria fail.

## JSON output

```bash
newb ./docs --format json > report.json
```

Top-level shape:

```json
{
  "newb_signature": { "tool": "newb", "version": "0.26.7", ... },
  "package": "<dirname>",
  "template": "python-package",
  "runtime_info": { "newb_version": "0.26.7", "runtime": "docker", ... },
  "what_for": "...",
  "problems_solved": "...",
  "quick_start": "...",
  "when_not_to_use": "...",
  "post_install_check": "INSTALL: ok\nIMPORT: ok\n...",
  "post_install_check_parsed": { "install": "ok", "import": "ok", "cli": "ok" },
  "prompt_injection_check": "FOUND: no\n...",
  "prompt_injection_check_parsed": { "found": false, "found_raw": "no" },
  "tests":         [ ...optional, present if tests_newb.yaml exists ],
  "tests_summary": { "passed": 3, "total": 4 }
}
```

The `<key>_parsed` siblings are populated by host-side parsers
(`newb._parsers`). They prefer the agent's fenced ` ```newb-json `
trailer when present; otherwise they regex over the prose. Off-script
replies yield `"unknown"` instead of raising.

## `newb gate` — declarative CI criteria

```bash
newb ./docs --format json > report.json
newb gate report.json
```

Default criteria:

- `post_install_check.install == "ok"`
- `post_install_check.import == "ok"`
- `prompt_injection_check.found == false`

Override per-project in `pyproject.toml`:

```toml
[tool.newb.gate.post_install_check]
install = "ok"
import  = "ok"
cli     = ["ok", "n/a"]   # list = any-of

[tool.newb.gate.prompt_injection_check]
found = false
```

Pass `-` as the report path to read from stdin:

```bash
newb ./docs --format json | newb gate -
```

`runs_per_prompt > 1` produces a list of parsed dicts; the gate
requires ALL runs to pass.

## Markdown output

```bash
newb ./docs --format markdown >> README.md
```

`render_markdown(report)` produces a "Skills Quality (verified by
agent)" block with the canonical Q&A pairs, a `runtime_info` YAML
block, and (if present) a Boundary tests section. The footer carries
the `newb_signature` (version + PyPI/GitHub URLs).

## GitHub Actions example

```yaml
- name: Verify docs (newb)
  env:
    NEWB_ANTHROPIC_API_KEY: ${{ secrets.NEWB_ANTHROPIC_API_KEY }}
  run: |
    pip install newb[yaml]
    newb ./src/$PKG/_skills/$PKG --format json > report.json
    cat report.json
    newb gate report.json   # exit 1 on install/import/injection failure
```

For badge-only adoption (no hard gating), see
[`08_ci-badge.md`](08_ci-badge.md).

## Patterns

| Goal | How |
|---|---|
| Update README on every push | `newb ... --format markdown > README.md.newb && diff README.md.newb README.md \|\| commit` |
| Block PRs on install failure | `newb gate report.json` (default criteria cover this) |
| Block PRs on injection finding | `newb gate report.json` (default criteria cover this) |
| Per-project criteria | `[tool.newb.gate.<question>]` tables in `pyproject.toml` |
| Stability monitoring | `--runs 5` → gate requires ALL runs to pass |
| Multi-package scan | one workflow matrix entry per `_skills/<pkg>/` directory |
| Hard isolation in CI | `--runtime docker` (image pre-pulled in a setup step) |

## Legacy `jq` pattern

The old recipe still works:

```bash
jq -e '.post_install_check_parsed.install == "ok"' report.json
```

But `newb gate` is the supported path forward.
