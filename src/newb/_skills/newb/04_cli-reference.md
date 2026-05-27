---
description: |
  [TOPIC] newb CLI Reference
  [DETAILS] Top-level subcommands of the `newb` CLI — `newb <package>`, gate, env, install, mcp, skills, templates, list-python-apis.
tags: [newb-cli-reference]
---

# CLI Reference

`newb` is the entry point installed by `pip install newb`.
The `scitex-newb` alias is identical.

## Primary form

```bash
newb <package>                              # current dir, git URL, or path
```

This is the bare invocation — newb runs the canonical-question prompts
against the target inside a sandboxed container.

## Subcommands

| Command                              | Purpose                                              |
|--------------------------------------|------------------------------------------------------|
| `newb <target>`                      | Probe a package (default subcommand)                 |
| `newb gate <report.json>`            | Declarative CI criteria (pass/fail from report)      |
| `newb show-env-template`             | Emit copy-pasteable `NEWB_*` env-var `.src` template |
| `newb install-shell-completion`      | Install shell completion (bash / zsh / fish)         |
| `newb print-shell-completion`        | Print completion script to stdout                    |
| `newb dev install`                   | Scaffold CI workflow + set secret on a repo          |
| `newb dev set-secret`                | Push `NEWB_ANTHROPIC_API_KEY` to a repo secret       |
| `newb dev scaffold-workflow`         | Drop `.github/workflows/newb.yml` into a repo        |
| `newb mcp start`                     | Start the MCP server (stdio) for AI agents           |
| `newb skills list`                   | List embedded skill pages                            |
| `newb skills get <ID>`               | Retrieve one skill page                              |
| `newb skills install`                | Copy skill leaves into `~/.claude/skills/newb/`      |
| `newb templates`                     | List / inspect the canonical-question templates      |
| `newb list-python-apis`              | Inventory the (small) Python API surface             |

## Common options

| Option                | Default     | Notes                                         |
|-----------------------|-------------|-----------------------------------------------|
| `--model`             | haiku-4-5   | Claude model id                               |
| `--runs`              | 1           | Repeat each prompt N times                    |
| `--template`          | python-pkg  | `python-package` / `cli-tool`                 |
| `--format`            | json        | `json` / `markdown`                           |
| `--runtime`           | docker      | `docker` / `podman` / `apptainer`             |
| `--scope`             | all         | `all` (full agentic) or `docs` (read-only)    |
| `--install-mode`      | editable    | `editable` / `wheel` / `pypi`                 |
| `--pip-cache`         | unset       | Host pip cache dir (local-dev speed-up)       |
| `--harden-memory`     | unlimited   | Container memory cap (e.g. `2g`)              |
| `--harden-cpus`       | unlimited   | CPU core cap                                  |
| `--harden-pids-limit` | unlimited   | PID cap                                       |
| `-v` / `--verbose`    | 0           | Verbosity level (count flag, up to -vvv)      |

## Examples

```bash
newb .                                      # current project, docker
newb . --format markdown                    # readable
newb https://github.com/u/r.git             # git URL — shallow-clones
newb . --runtime apptainer                  # HPC variant
newb . --install-mode wheel                 # build + install a wheel
newb . --pip-cache ~/.cache/newb-pip        # local-dev: warm pip cache
newb gate report.json                       # CI gating vs [tool.newb.gate]
newb show-env-template -o ~/.config/newb/local.src
newb install-shell-completion               # auto-detected shell
newb mcp start                              # speak MCP/stdio for an AI agent
newb dev install owner/repo                 # CI bootstrap
```

See [15_ci-integration.md](15_ci-integration.md) for CI gating recipes and
[12_isolation-runtimes.md](12_isolation-runtimes.md) for runtime details.
