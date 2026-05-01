---
name: newb
description: Test your Python package through the eyes of a fresh AI agent. `newb <docs-or-skills-dir>` spins up a sandboxed `claude-agent-sdk` session (setting_sources=[], allowed_tools=["Read"], cwd=staged copy) that reads only your documentation and answers four canonical questions — what for, problems solved, quick start, when not to use — plus any author-defined prompts in `tests_newb.yaml`. JSON or markdown output for CI. Three isolation runtimes — host (subprocess, soft), docker / apptainer (real filesystem + network namespace, hard). The first-class reader of a modern package is an agent; newb tests docs through the actual reader. Use whenever the user asks "is my docs good enough?", "would an agent understand this?", "can a newcomer use my package from docs alone?", "verify package docs", "test my package's discoverability", "audit skills quality", or works on multi-package ecosystem doc quality. Do NOT use as a unit-test runner (use pytest), as a benchmark for the model itself (use eval frameworks), or for code coverage (use pytest-cov).
primary_interface: cli
interfaces:
  python: 1
  cli: 1
  mcp: 0
  skills: 7
  hook: 0
  http: 0
tags: [newb, scitex-package]
---

# newb — newbie-agent docs verifier

A fresh AI agent reads only your `_skills/` (or `docs/`) and tries to use
your package. If it succeeds, your docs work. If it fails, the failing
prompt names the gap.

## Two patterns

| Pattern | Use when | Module |
|---|---|---|
| **One-shot probe** (`newb <dir>`) | Smoke check on a single docs/skills tree | `newb._cli`, `newb.run` |
| **Author tests** (`tests_newb.yaml`) | Per-package boundary tests (must contain X, must NOT hallucinate Y, must satisfy judge criteria) | `newb._verify._load_tests`, `_grade` |

## Sub-skills

- [01_quick-start.md](01_quick-start.md) — install, minimal CLI + Python forms, output formats
- [02_canonical-questions.md](02_canonical-questions.md) — the 4 questions newb always asks + why those four
- [03_author-tests.md](03_author-tests.md) — `tests_newb.yaml` schema, substring graders, LLM judge, double grading
- [04_isolation-runtimes.md](04_isolation-runtimes.md) — `host` / `docker` / `apptainer`; what each fences off
- [05_source-resolution.md](05_source-resolution.md) — local paths, git URLs, the `_skills/` → `docs/` → root detection order
- [06_when-not-to-use.md](06_when-not-to-use.md) — explicit boundaries (not a test runner, not a model benchmark, not a coverage tool)
- [07_ci-integration.md](07_ci-integration.md) — JSON output for CI, markdown for README, exit codes, `tests_summary`

## Quick example

```bash
newb ./docs                           # one-shot probe → JSON
newb ./docs --format markdown         # readable for humans
newb https://github.com/u/r.git --runtime docker   # hard isolation
```

```python
import newb
report = newb("./docs")               # bare-module callable
print(newb.render_markdown(report))
```

## Auth

Set `ANTHROPIC_API_KEY` (canonical, ToS-clean) or rely on a local
`~/.claude/` OAuth login on personal machines (not sanctioned for
redistributed products).
