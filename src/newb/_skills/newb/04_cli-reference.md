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

| Command                   | Purpose                                              |
|---------------------------|------------------------------------------------------|
| `newb <target>`           | Probe a package (default subcommand)                 |
| `newb gate <target>`      | Declarative CI criteria (pass/fail thresholds)       |
| `newb install`            | Install / verify a container runtime                 |
| `newb env`                | Inspect / generate `.env` for `NEWB_*` vars          |
| `newb mcp start`          | Start the MCP server (stdio) for AI agents           |
| `newb skills list`        | List embedded skill pages                            |
| `newb skills get <ID>`    | Retrieve one skill page                              |
| `newb templates`          | List / inspect the canonical-question templates      |
| `newb list-python-apis`   | Inventory the (small) Python API surface             |

## Common options

| Option                | Default     | Notes                                         |
|-----------------------|-------------|-----------------------------------------------|
| `--runtime`           | auto        | `docker` / `podman` / `apptainer`             |
| `--scope`             | `all`       | `all` (full agentic) or `docs` (read-only)    |
| `--format`            | `json`      | `json` / `markdown`                           |
| `--tests <PATH>`      | none        | Author-tests yaml; enables grading            |

## Examples

```bash
newb .                                      # current project, docker
newb . --format markdown                    # readable
newb https://github.com/u/r.git             # git URL — shallow-clones
newb . --runtime apptainer                  # HPC variant
newb gate . --tests tests_newb.yaml         # CI gating
newb mcp start                              # speak MCP/stdio for an AI agent
```

See [15_ci-integration.md](15_ci-integration.md) for CI gating recipes and
[12_isolation-runtimes.md](12_isolation-runtimes.md) for runtime details.
