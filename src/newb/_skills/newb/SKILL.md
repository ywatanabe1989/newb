---
name: newb
description: Test your Python package through the eyes of a fresh AI agent. `newb <project-dir>` spins up a sandboxed container (docker default, apptainer for HPC), stages the project respecting .gitignore, and runs a `claude-agent-sdk` session at `/work/project` with FULL agentic permissions (Read+Write+Edit+Bash+Glob+Grep, acceptEdits) — agent can `pip install -e .`, `python -c "import pkg"`, `<pkg> --help`, write an example. The container IS the boundary; SDK options inside grant the agent enough power to actually try the package. The agent answers four canonical questions — what for, problems solved, quick start, when not to use — plus any author-defined prompts in `tests_newb.yaml`. JSON or markdown output for CI. The first-class reader of a modern package is an agent; newb tests docs through the actual reader. Use whenever the user asks "is my docs good enough?", "would an agent understand this?", "can a newcomer use my package from docs alone?", "verify package docs", "audit skills quality". Do NOT use as a unit-test runner (use pytest), as a benchmark for the model (use eval frameworks), or for code coverage (use pytest-cov).
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
| **Author tests** (`tests_newb.yaml`) | Per-package boundary tests (must contain X, must NOT hallucinate Y, must satisfy judge criteria) | `newb._try._load_tests`, `_grade` |

## Sub-skills

- [01_quick-start.md](01_quick-start.md) — install, minimal CLI + Python forms, output formats
- [02_canonical-questions.md](02_canonical-questions.md) — the 4 questions newb always asks + why those four
- [03_author-tests.md](03_author-tests.md) — `tests_newb.yaml` schema, substring graders, LLM judge, double grading
- [04_isolation-runtimes.md](04_isolation-runtimes.md) — `host` / `docker` / `apptainer`; what each fences off
- [05_source-resolution.md](05_source-resolution.md) — local paths, git URLs, the `_skills/` → `docs/` → root detection order
- [06_when-not-to-use.md](06_when-not-to-use.md) — explicit boundaries (not a test runner, not a model benchmark, not a coverage tool)
- [07_ci-integration.md](07_ci-integration.md) — JSON output for CI, markdown for README, exit codes, `tests_summary`
- [30_env-vars.md](30_env-vars.md) — every NEWB_-prefixed env var with type/default; explicit "what newb does NOT read"

## Quick example

```bash
newb .                               # current project — docker by default
newb . --format markdown             # readable for humans
newb https://github.com/u/r.git      # git URL — shallow-clones first
newb . --runtime apptainer           # HPC variant
```

```python
import newb
report = newb(".")                   # bare-module callable
print(newb.render_markdown(report))
```

## Container is the boundary, not the SDK options (newb 0.9)

newb runs in `docker` (default) or `apptainer`. Inside the container
the agent has FULL agentic permissions — Read+Write+Edit+Bash+Glob+
Grep, `permission_mode=acceptEdits`, max_turns=15 — so it can
actually try the package: `pip install -e .`, `python -c "import pkg"`,
`<pkg> --help`, write an example, run pytest. The container itself
is the real isolation boundary.

The `host` runtime was removed in 0.9 — full agentic permissions on
the host are unsafe (agent could `rm -rf` your projects, `pip install`
into the global env). Use a container.

## Auth

Set `NEWB_ANTHROPIC_API_KEY` (the only env var newb reads — no
upstream surprise from a stray `ANTHROPIC_API_KEY` in your shell).
The container runtimes forward it as `ANTHROPIC_API_KEY` so the SDK
inside picks it up.
