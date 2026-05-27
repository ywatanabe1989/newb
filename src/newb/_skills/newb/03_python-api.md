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
report = newb.run(".", runtime="docker", scope="all")
report = newb.run("https://github.com/u/r.git")
```

| Argument         | Default     | Purpose                                          |
|------------------|-------------|--------------------------------------------------|
| `skills_dir`     | required    | Local path or git URL                            |
| `model`          | haiku-4-5   | Claude model id                                  |
| `runs_per_prompt`| 1           | Repeat each prompt N times                       |
| `runtime`        | docker      | `docker` / `podman` / `apptainer`                |
| `template`       | python-pkg  | `python-package` / `cli-tool`                    |
| `install_mode`   | editable    | `editable` / `wheel` / `pypi`                    |
| `scope`          | all         | `all` (full agentic) or `docs` (read-only)       |
| `pip_cache_dir`  | None        | Host pip cache dir (local-dev speed-up)          |
| `verbosity`      | 0           | Verbosity level (0-3)                            |

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
