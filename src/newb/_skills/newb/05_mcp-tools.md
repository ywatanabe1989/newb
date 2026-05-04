---
description: |
  [TOPIC] MCP Tools
  [DETAILS] newb's MCP server exposes the same `newb()` probe + helpers via stdio for AI agents. Started with `newb mcp start`.
tags: [newb-mcp-tools]
---

# MCP Tools

`newb` ships a small MCP server (stdio) for AI-agent integration.

## Start

```bash
newb mcp start                              # stdio MCP server
```

Inside an MCP-aware client (Claude Desktop, Cursor, etc.), register the
server with the command above as the launcher.

## Tools

| Tool                | Purpose                                              |
|---------------------|------------------------------------------------------|
| `newb_run`          | Probe a target package (mirrors `newb <target>`)     |
| `newb_gate`         | Run gating with `tests_newb.yaml`                    |
| `newb_skills_list`  | List embedded skill pages                            |
| `newb_skills_get`   | Retrieve one skill page                              |
| `newb_templates`    | Inspect canonical-question templates                 |

## Tool inventory

```bash
newb mcp list-tools                         # machine-readable inventory
```

## See also

- [04_cli-reference.md](04_cli-reference.md) — CLI surface (the MCP tools wrap these)
- [01_installation.md](01_installation.md) — auth: `NEWB_ANTHROPIC_API_KEY` is forwarded into the container
