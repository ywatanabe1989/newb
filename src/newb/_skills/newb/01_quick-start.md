---
name: newb-quick-start
description: Install newb, run the minimal CLI form against any project (or git URL), render the JSON / markdown report, and call newb from Python. Covers the common flags (template, runtime, install-mode, scope, pip-cache).
tags: [newb]
---

# Quick Start

## Install

```bash
pip install newb              # core
pip install newb[yaml]        # + tests_newb.yaml support (pyyaml)
```

`claude-agent-sdk` (Anthropic, MIT) is pulled in automatically. Auth
via `NEWB_ANTHROPIC_API_KEY` (newb-owned namespace, no upstream
surprise). newb actively masks any stray `ANTHROPIC_API_KEY` so it
can't sneak in unintentionally. Both real API keys (`sk-ant-api03-…`)
and Claude Code OAuth access tokens (`sk-ant-oat01-…`) work on the
same code path.

## CLI

```bash
newb .                                      # current project
newb ./src/mypkg                            # any project tree
newb https://github.com/user/repo.git       # git URL — shallow-cloned

newb . --markdown                           # human-readable
newb . --markdown >> README.md
newb . --runs 3                             # repeat each question N times
newb . --template cli-tool                  # CLI-flavored question set
newb . --runtime podman                     # rootless podman
newb . --runtime apptainer                  # HPC
newb . --install-mode wheel                 # build + install a wheel
newb . --install-mode pypi                  # `pip install <pkg>` from PyPI
newb . --scope docs                         # read-only audit (no Bash)
newb . --pip-cache ~/.cache/newb-pip        # local-dev: warm pip cache
```

The CLI prints a JSON object (default) or a markdown block, then a
single stderr line summarising the test pass count (or
`smoke check complete` if there is no `tests_newb.yaml`).

## Subcommands (introspection)

```bash
newb templates list                         # built-in question sets
newb templates show python-package          # the actual prompts
newb skills list                            # newb's own skill leaves
newb mcp list-tools                         # MCP tools newb exposes
newb mcp start                              # run as MCP server (stdio)
newb env-template -o ~/.config/newb/local.src
newb list-python-apis                       # public Python surface
newb gate report.json                       # exit 0/1 vs [tool.newb.gate]
```

## Python

```python
import newb

# Bare-module callable (PEP 562) — equivalent to newb.run(...)
report = newb("./")
print(report["what_for"])

# Explicit form
report = newb.run(
    "./",
    model="claude-haiku-4-5",
    template="python-package",     # or "cli-tool"
    runtime="docker",
    install_mode="editable",
    scope="all",
    runs_per_prompt=1,
)

# Render the markdown form for paste-into-README:
print(newb.render_markdown(report))
```

## Output shape

```json
{
  "package": "your-package",
  "template": "python-package",
  "runtime_info": {"newb_version": "0.19.1", "runtime": "docker", ...},
  "what_for": "...one sentence...",
  "problems_solved": "| # | Problem | Solution | ... markdown table",
  "quick_start": "```python\n...\n```",
  "when_not_to_use": "...one or two sentences...",
  "post_install_check": "INSTALL: ok\nIMPORT: ok\nCLI: ok\nEVIDENCE: ...",
  "post_install_check_parsed": {"install": "ok", "import": "ok", "cli": "ok"},
  "prompt_injection_check": "FOUND: no\nEVIDENCE: none",
  "prompt_injection_check_parsed": {"found": false, "found_raw": "no"},
  "newb_signature": {"tool": "newb", "version": "0.24.0", ...}
}
```

`<key>_parsed` siblings (since 0.23.0) are populated by host-side
parsers and are what `newb gate` consults. Free-text replies stay
untouched. If `tests_newb.yaml` is present, the report also includes
`tests` and `tests_summary`.

## Project defaults via `[tool.newb]`

```toml
[tool.newb]
template = "python-package"
runtime = "docker"
scope = "all"
install_mode = "wheel"
runs = 1

# Optional: forward MCP servers to the in-container agent so it has
# the same tool surface as a normal Claude Code session. Validated
# host-side — stdio commands must be a basename or container-resident
# absolute path.
[tool.newb.mcp_servers.example]
type = "stdio"
command = "my-mcp-server"

# Optional: hard CI criteria (since 0.24.0) — `newb gate report.json`
# evaluates these against `<key>_parsed` fields. Lists mean any-of.
[tool.newb.gate.post_install_check]
install = "ok"
import  = "ok"
cli     = ["ok", "n/a"]

[tool.newb.gate.prompt_injection_check]
found = false
```

CLI flags > `[tool.newb]` > built-in defaults.
