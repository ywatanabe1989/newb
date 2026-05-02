---
name: newb-quick-start
description: Install newb, run the minimal CLI form against any docs directory, render the JSON or markdown report, and call newb from Python (bare-module shortcut + explicit run() form).
tags: [newb, scitex-package]
---

# Quick Start

## Install

```bash
pip install newb              # core
pip install newb[yaml]        # + tests_newb.yaml support (pyyaml)
```

`claude-agent-sdk` (Anthropic, MIT) is pulled in automatically. Auth via
`NEWB_ANTHROPIC_API_KEY` (newb-owned namespace, no upstream surprise) or
a local `~/.claude/` OAuth login on personal machines. newb actively
masks any stray `ANTHROPIC_API_KEY` so it can't sneak in unintentionally.

## CLI

```bash
newb ./docs                             # any dir of .md files
newb ./src/mypkg/_skills/mypkg          # standard SciTeX layout
newb https://github.com/user/repo.git   # git URL (shallow-cloned)

newb ./docs --format markdown           # human-readable
newb ./docs --format markdown >> README.md
newb ./docs --runs 3                    # ask each question 3 times → list
newb ./docs --runtime docker            # hard isolation
newb ./docs --model claude-sonnet-4-6   # override default haiku-4-5
```

The CLI prints a JSON object (default) or a markdown block, then a
single stderr line summarising the test pass count (or `smoke check
complete` if there is no `tests_newb.yaml`).

## Python

```python
import newb

# Bare-module callable (PEP 562) — equivalent to newb.run(...)
report = newb("./src/mypkg/_skills/mypkg")
print(report["what_for"])

# Explicit form (mirrors pytest.main convention)
report = newb.run("./docs", model="claude-haiku-4-5", runs_per_prompt=1)

# Render the markdown form for paste-into-README:
print(newb.render_markdown(report))
```

## Output shape

```json
{
  "package": "mypkg",
  "what_for": "...one sentence...",
  "problems_solved": "| # | Problem | Solution | ... markdown table",
  "quick_start": "```python\n...\n```",
  "when_not_to_use": "...one or two sentences..."
}
```

If `tests_newb.yaml` is present the report also includes `tests` and
`tests_summary`.
