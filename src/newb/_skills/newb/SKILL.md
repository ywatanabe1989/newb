---
name: newb
description: Test your Python package through the eyes of a fresh AI agent. `newb <docs-or-skills-dir>` spins up a sandboxed `claude-agent-sdk` session (setting_sources=[], allowed_tools=["Read"], cwd=staged copy) that reads only your documentation and answers four canonical questions — what for, problems solved, quick start, when not to use — plus any author-defined prompts in `tests_newb.yaml`. JSON or markdown output for CI integration. Three isolation runtimes — `host` (soft), `docker`/`apptainer` (hard). The first-class reader of a modern package is an agent; newb tests docs through the actual reader. Use whenever the user asks "is my docs good enough?", "would an agent understand this?", "can a newcomer use my package from docs alone?", "verify package docs", "test my package's discoverability", "audit skills quality", or works on multi-package ecosystem doc quality.
primary_interface: cli
interfaces:
  python: 1
  cli: 1
  mcp: 0
  skills: 1
  hook: 0
  http: 0
tags: [newb, scitex-package]
---

# newb — newbie-agent docs verifier

A fresh AI agent reads only your docs and tries to use your package. If
it succeeds, your docs work. The verification surface is fully
sandboxed: `setting_sources=[]`, `allowed_tools=["Read"]`,
`cwd=<staged copy>` — no host CLAUDE.md, no Bash, no Write.

## When to reach for newb

| Want to know… | Run |
|---|---|
| Are my docs sufficient for a newcomer? | `newb ./docs` |
| Does the SciTeX-style `_skills/<pkg>/` tree work? | `newb ./src/<pkg>/_skills/<pkg>` |
| Do public-repo docs survive a fresh clone? | `newb https://github.com/user/repo.git --runtime docker` |
| Do my custom prompts pass? | put them in `tests_newb.yaml` |

## Sub-skills

(none yet — single-file SKILL.md is sufficient at this scale; split into
`NN_topic.md` companions if SK301 budget is exceeded later)

## Quick example

```bash
newb ./docs --format json | jq .
newb ./docs --runtime docker > report.txt
```

```python
import newb
report = newb("./docs")
print(newb.render_markdown(report))
```

## Author tests (`tests_newb.yaml`)

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  expect_contains: ["does not"]
  judge: "Must redirect to an alternative tool, not hallucinate."
```

## Auth

`export ANTHROPIC_API_KEY=sk-ant-api03-...` is the canonical ToS-clean
path. Local `claude` OAuth also works on personal machines but is not
sanctioned for redistributed products.
