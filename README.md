# newb

<p align="center"><img src="./assets/newb-logo.png" width="220" alt="newb mascot"/></p>

A fresh AI agent reads only your docs and tries to use your package. If it
succeeds, your docs work.

## How it works

```
┌──────────────────────┐    ┌──────────────────────────────┐    ┌──────────────────────┐
│   Your package       │    │   sac (scitex-agent-         │    │   Report             │
│                      │    │   container)                 │    │                      │
│   ./docs/   or       │    │                              │    │   what_for           │
│   ./_skills/<pkg>/   │ →  │   spins up a fresh Claude    │ →  │   problems_solved    │
│   tests_newb.yaml    │    │   Code session (local /      │    │   quick_start        │
│   (optional)         │    │   docker / apptainer) with   │    │   when_not_to_use    │
│                      │    │   only your skills mounted   │    │   tests[] (pass/fail)│
└──────────────────────┘    └──────────────────────────────┘    └──────────────────────┘
            │                            ▲
            │                            │  newb POSTs N prompts via A2A JSON-RPC
            └────────── stages ──────────┘
                                         (one container, N requests)
```

newb owns the **test schema** (4 canonical questions + `tests_newb.yaml`
+ graders + report rendering). sac owns **everything else**: runtime
selection, auth, isolation, Claude Code session lifecycle. newb only
speaks A2A.

## Install

```bash
pip install newb
```

`scitex-agent-container` is pulled in as a dependency.

## Use

```bash
newb ./docs                                # any dir of .md files
newb ./src/mypkg/_skills/mypkg             # standard SciTeX layout
newb https://github.com/user/repo.git      # git URL — shallow-clones
newb ./docs --format markdown >> README.md
```

Asks a fresh Claude Code agent four canonical questions (what for /
problems solved / quick start / when not to use), plus any
author-defined tests in `tests_newb.yaml`. Output: JSON (for CI) or
markdown.

### Author tests (`tests_newb.yaml`)

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  expect_contains: ["does not"]
  judge: "Must redirect to an alternative tool, not hallucinate."
```

Each test combines optional substring grading and an optional LLM judge.

## Auth, runtime, isolation

All handled by sac — see
[scitex-agent-container](https://github.com/ywatanabe1989/scitex-agent-container)
for credential setup, runtime backends (local / docker / apptainer /
ssh-remote / slurm), and isolation primitives. newb's job ends at "POST
the prompt, parse the response."

## Library

```python
import newb
report = newb("./docs")
print(newb.render_markdown(report))
```

## Requirements

- Python 3.10+
- `scitex-agent-container` (auto-installed) — see its README for one-time
  account/credential setup

## License

AGPL-3.0-only.
