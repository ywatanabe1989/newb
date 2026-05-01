---
name: newb-ci-integration
description: Wire newb into CI — JSON output for parsing, markdown for README updates, exit-code semantics, tests_summary parsing, and a sample GitHub Actions step.
tags: [newb, scitex-package]
---

# CI integration

newb is designed to be one shell line in a CI step. The CLI's two
output formats (`json` for machines, `markdown` for paste-into-README)
cover both common needs.

## Exit codes

The CLI exits **0** as long as the SDK call completed and produced a
report. Test failures (`expect_contains` / `judge` returning `false`)
do **not** fail the process — they appear in the JSON `tests` array
and the stderr summary line.

This is intentional: newb reports, your CI decides. Wrap with `jq` for
fail-on-test-failure semantics (see below).

## JSON output

```bash
newb ./docs --format json > report.json
```

The shape is:

```json
{
  "package": "<dirname>",
  "what_for": "...",
  "problems_solved": "...",
  "quick_start": "...",
  "when_not_to_use": "...",
  "tests":         [ ...optional, present if tests_newb.yaml exists ],
  "tests_summary": { "passed": 3, "total": 4 }
}
```

## Markdown output

```bash
newb ./docs --format markdown >> README.md
```

`render_markdown(report)` produces a "Skills Quality (verified by
agent)" block with timestamp, the four canonical Q&A pairs, and (if
present) a Boundary tests section listing each test with PASS/FAIL.

## GitHub Actions example

```yaml
- name: Verify docs (newb)
  env:
    NEWB_ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    pip install newb[yaml]
    newb ./src/$PKG/_skills/$PKG --format json --runs 2 > /tmp/newb.json
    cat /tmp/newb.json
    # Fail the step if any author test failed:
    jq -e '.tests_summary.passed == .tests_summary.total // true' \
       /tmp/newb.json > /dev/null
```

The `// true` clause makes the gate pass when no `tests_summary` field
is present (no `tests_newb.yaml` defined yet — pure smoke check).

## Patterns

| Goal | How |
|---|---|
| Update README on every push | `newb ... --format markdown > README.md.newb && diff README.md.newb README.md \|\| commit` |
| Block PRs that break docs | `jq -e` on `tests_summary` (above) |
| Stability monitoring | `--runs 5` + parse the lists, alert if pass rate drops |
| Multi-package scan | one workflow matrix entry per `_skills/<pkg>/` directory |
| Hard isolation in CI | `--runtime docker` (image pre-pulled in a setup step) |

## Sample stderr

```
🐝 newb: probing ./docs ...
🐝✅ 3/3 tests passed
```

Or, with no `tests_newb.yaml`:

```
🐝 newb: probing ./docs ...
🐝 smoke check complete (no tests_newb.yaml found)
```
