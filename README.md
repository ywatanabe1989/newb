# newb

<p align="center"><img src="./assets/newb-logo.png" width="220" alt="newb mascot"/></p>

A fresh AI agent reads only your docs and tries to use your package. If it
succeeds, your docs work.

## How it works

```
┌──────────────────────┐         ┌────────────────────────────────────┐         ┌──────────────────────┐
│   Your package       │         │   Fresh agent                      │         │   Report             │
│                      │  newb   │                                    │  asks   │                      │
│   ./docs/  or        │  spins  │   docker / local / apptainer       │  4 + N  │   what_for           │
│   ./_skills/<pkg>/   │   up    │   isolated HOME (no ~/.claude)     │  ────→  │   problems_solved    │
│   tests_newb.yaml    │         │   sees ONLY your docs              │  reads  │   quick_start        │
│   (optional)         │         │   no internet to your real session │  back   │   when_not_to_use    │
└──────────────────────┘         └────────────────────────────────────┘         │   tests[] (pass/fail)│
         │                                       ▲                              └──────────────────────┘
         └───────────── stages skills ───────────┘
                       (read-only mount)
```

The agent has no prior context — it sees only what you ship. If it answers
the 4 canonical questions correctly and your `tests_newb.yaml` graders
pass, your docs work for the realistic case of a brand-new user (or AI).

## Install

```bash
pip install newb
```

## Use

```bash
newb ./docs                                     # any dir of .md files
newb https://github.com/user/repo.git           # git URL — auto-clones
newb ./docs --format markdown >> README.md
newb ./docs --runtime local --auth claude-code  # host subprocess
```

Asks a fresh Claude agent four canonical questions (what for / problems
solved / quick start / when not to use), plus any author-defined tests in
`tests_newb.yaml`. Output: JSON (for CI) or markdown.

### Author tests (`tests_newb.yaml`)

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  expect_contains: ["does not"]
  judge: "Must redirect to an alternative tool, not hallucinate."
```

Each test combines optional substring grading and an optional LLM judge.

## Runtime · Auth

| `--runtime` | what                                          |
|-------------|-----------------------------------------------|
| `docker`    | default — clean container, no host leakage    |
| `local`     | host subprocess with isolated `HOME`          |
| `apptainer` | HPC (planned)                                 |

| `--auth`      | what                                          |
|---------------|-----------------------------------------------|
| `api-key`     | default — uses `$ANTHROPIC_API_KEY`           |
| `claude-code` | copies host `~/.claude/.credentials*`         |

## Library

```python
import newb
report = newb("./docs")
print(newb.render_markdown(report))
```

## Requirements

- `docker` on PATH (or `claude` CLI if `--runtime local`)
- `$ANTHROPIC_API_KEY` (or `--auth claude-code`)
- Python 3.10+

## License

AGPL-3.0-only.
