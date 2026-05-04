---
description: |
  [TOPIC] Python API
  [DETAILS] Public callables — `newb(...)` (bare-module call shortcut for `run`), `run()`, and `render_markdown()`.
tags: [newb-python-api]
---

# Python API

The Python surface is intentionally tiny — newb is primarily a CLI tool.

## Imports

```python
import newb
from newb import run, render_markdown
```

## `newb(target, ...)` / `newb.run(target, ...)`

Probe a target with a fresh agent in a sandboxed container.

```python
import newb

report = newb(".")                            # bare-module call shortcut
report = newb.run(".", runtime="docker", scope="all", format="json")
report = newb.run("https://github.com/u/r.git")
```

| Argument   | Default     | Purpose                                          |
|------------|-------------|--------------------------------------------------|
| `target`   | required    | Local path or git URL                            |
| `runtime`  | auto        | `docker` / `podman` / `apptainer`                |
| `scope`    | `"all"`     | `"all"` (full agentic) or `"docs"` (read-only)   |
| `format`   | `"json"`    | `"json"` / `"markdown"`                          |
| `tests`    | None        | Path to `tests_newb.yaml`; enables author tests  |

Returns a dict with per-prompt results, judge gradings (if `tests=`), and
overall pass/fail.

## `render_markdown(report) -> str`

Render a JSON report into human-readable markdown.

```python
report = newb(".")
print(newb.render_markdown(report))
```

## What's NOT exposed

newb deliberately keeps its CLI surface much wider than its Python surface.
Use `newb` (the CLI) for `gate`, `init`, `list-templates`, etc.
See [04_cli-reference.md](04_cli-reference.md).

## Boundaries

newb is NOT a unit-test runner, model benchmark, or coverage tool —
see [14_when-not-to-use.md](14_when-not-to-use.md).
