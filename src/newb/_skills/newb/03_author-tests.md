---
name: newb-author-tests
description: Per-package boundary tests via tests_newb.yaml — schema (prompt, expect_contains, expect_excludes, judge), substring grading, LLM judge, double grading semantics.
tags: [newb]
---

# Author tests — `tests_newb.yaml`

Per-package boundary tests. Place `tests_newb.yaml` in the same
directory you point `newb` at, and each entry becomes an extra prompt
with author-defined grading.

## Schema

```yaml
- name: optional human label              # default: test_<index>
  prompt: "the question to ask the agent" # required (legacy alias: question)
  expect_contains: ["substring1", ...]    # optional — case-insensitive
  expect_excludes: ["substring1", ...]    # optional — case-insensitive
  judge: "criteria text for an LLM judge" # optional
```

A test entry must define **at least one** of `expect_contains`,
`expect_excludes`, or `judge`. An entry with none of them is treated as
auto-pass (smoke probe).

## Two graders, AND-combined

```
substring grader (if expect_contains or expect_excludes)
    ↓
    contains_ok = all(s in answer.lower() for s in expect_contains)
    excludes_ok = all(s not in answer.lower() for s in expect_excludes)
    substring_passed = contains_ok AND excludes_ok

judge grader (if judge)
    ↓
    Calls a 2nd Claude query with:
      "PASS: <reason>" or "FAIL: <reason>" — be strict.
      CRITERIA: <judge text>
      ANSWER:   <agent answer>
    Verdict = first 4 chars upper-case start with "PASS"

overall passed = substring_passed AND judge_passed
                 (each grader's check is skipped if not configured)
```

## Examples

### Substring-only (cheap, deterministic)

```yaml
- name: mentions_python_version
  prompt: What Python versions does this package support?
  expect_contains: ["3.10", "3.11", "3.12", "3.13"]
```

### Excludes (anti-hallucination guard)

```yaml
- name: no_fictional_subcommand
  prompt: How do I run things in parallel with this tool?
  expect_excludes: ["--parallel", "--workers"]   # this tool has neither
```

### Judge (semantic check, not substring)

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  judge: "Must redirect to an alternative tool, not invent a flag."
```

### Both (substring as fast filter, judge as final word)

```yaml
- name: documents_isolation
  prompt: Is the agent sandboxed from my host filesystem?
  expect_contains: ["docker", "apptainer"]
  judge: "Answer must distinguish soft (host) from hard (container) isolation."
```

## Output

When `tests_newb.yaml` is present, the report adds:

```json
{
  "tests": [
    {"name": "...", "prompt": "...", "answer": "...", "passed": true,
     "substring": {"contains_ok": true, "excludes_ok": true, "passed": true},
     "judge":     {"passed": true, "reason": "PASS: matches"}}
  ],
  "tests_summary": {"passed": 3, "total": 4}
}
```

The CLI also emits a stderr summary line (`🐝✅ 3/4 tests passed`).

