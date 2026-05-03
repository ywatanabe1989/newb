---
name: newb
description: Newbie-agent package tester — a fresh AI agent reads only your docs and tries to use your package; if it succeeds, your docs work. `newb <project-dir>` spins up a sandboxed container (docker default, podman for rootless, apptainer for HPC), stages the project respecting .gitignore, and runs ONE batched `claude-agent-sdk` session at `/work/project` with FULL agentic permissions (Read+Write+Edit+Bash+Glob+Grep, `bypassPermissions` for `--scope all`) — agent can `pip install -e .`, `python -c "import pkg"`, `<pkg> --help`, write an example. The container IS the boundary; SDK options inside grant the agent enough power to actually try the package. The agent answers six canonical questions per template — `python-package`: what_for, problems_solved, quick_start, when_not_to_use, post_install_check, prompt_injection_check; `cli-tool`: what_for, install_and_help, subcommand_tree, typical_usage, common_pitfall, prompt_injection_check — plus any author-defined prompts in `tests_newb.yaml`. JSON or markdown output for CI. The first-class reader of a modern package is an agent; newb mimics a newbie *user* using the agent as the lens. Use whenever the user asks "is my docs good enough?", "would an agent understand this?", "can a newcomer use my package from docs alone?", "verify package docs", "audit skills quality", "test install + import + smoke-run". Do NOT use as a unit-test runner (use pytest), as a benchmark for the model (use eval frameworks), or for code coverage (use pytest-cov).
primary_interface: cli
interfaces:
  python: 1
  cli: 1
  mcp: 0
  skills: 8
  hook: 0
  http: 0
tags: [newb]
---

# newb — newbie-agent package tester

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
- [02_canonical-questions.md](02_canonical-questions.md) — the 6-question templates (`python-package`, `cli-tool`) + why those questions
- [03_author-tests.md](03_author-tests.md) — `tests_newb.yaml` schema, substring graders, LLM judge, double grading
- [04_isolation-runtimes.md](04_isolation-runtimes.md) — `docker` / `podman` / `apptainer`; one-container-per-run batched execution; configurable hardening; pip cache
- [05_source-resolution.md](05_source-resolution.md) — local paths, git URLs, the `_skills/` → `docs/` → root detection order
- [06_when-not-to-use.md](06_when-not-to-use.md) — explicit boundaries (not a test runner, not a model benchmark, not a coverage tool)
- [07_ci-integration.md](07_ci-integration.md) — JSON / markdown output, `<key>_parsed` structured fields, `newb gate` declarative CI criteria
- [08_ci-badge.md](08_ci-badge.md) — `Newb | passing` GitHub Actions badge adoption
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

## Container is the boundary, not the SDK options

newb runs in `docker` (default), `podman` (rootless), or `apptainer`
(HPC). Inside the container the agent has FULL agentic permissions —
Read+Write+Edit+Bash+Glob+Grep, `permission_mode="bypassPermissions"`
(for `--scope all`, the default), max_turns=15 — so it can actually
try the package: `pip install -e .`, `python -c "import pkg"`,
`<pkg> --help`, write an example, run pytest. `--scope docs`
switches to read-only audit (`acceptEdits` + `Read/Glob/Grep`
allowlist). The container itself is the real isolation boundary.

Since 0.19.0, all template prompts run in **one** container per
`newb` invocation — per-prompt `query()` keeps conversations
isolated, but on-disk state (`pip install -e .` from
`post_install_check`) persists across prompts within the run.

The `host` runtime was removed in 0.9 — full agentic permissions on
the host are unsafe (agent could `rm -rf` your projects, `pip install`
into the global env). Use a container.

## Auth

Set `NEWB_ANTHROPIC_API_KEY` (the only env var newb reads — no
upstream surprise from a stray `ANTHROPIC_API_KEY` in your shell).
The container runtimes forward it as `ANTHROPIC_API_KEY` so the SDK
inside picks it up.
