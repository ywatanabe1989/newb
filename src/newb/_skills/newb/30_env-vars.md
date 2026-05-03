---
description: |
  [TOPIC] Env Vars
  [DETAILS] Environment variables read by newb at import / runtime. NEWB_-prefixed only — never silently inherits the upstream ANTHROPIC_API_KEY. Documents auth (API key + OAuth Pro/Max), runtime (docker image, model), and SDK-internal (cwd, skills path) vars.
tags: [newb-env-vars]
---

# newb — Environment Variables

newb owns its own env namespace (`NEWB_` prefix). It NEVER silently
inherits an upstream `ANTHROPIC_API_KEY` from the user's shell — the
host runtime actively masks it for the duration of the SDK call so
the bundled CLI cleanly falls through to OAuth or fails. Container
runtimes hard-fail without a NEWB_-prefixed key.

## Auth (one var, opt-in)

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `NEWB_ANTHROPIC_API_KEY` | Opaque token. Forwarded verbatim into the container, where the in-container runner promotes it to `ANTHROPIC_API_KEY` for the bundled CLI. The Anthropic backend accepts both `sk-ant-api03-…` (real API keys) and `sk-ant-oat01-…` (Claude Code Pro / Max OAuth access tokens) on the same Authorization header — newb does not dispatch on prefix. | unset | secret |

OAuth users on Claude Code Pro / Max can extract the access token
from the local credentials file:

```bash
export NEWB_ANTHROPIC_API_KEY=$(jq -r .claudeAiOauth.accessToken ~/.claude/.credentials.json)
```

## Runtime (image + model overrides)

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `NEWB_DOCKER_IMAGE` | Override the container image used by `--runtime docker / podman / apptainer`. | `ghcr.io/ywatanabe1989/newb-runner:<newb-version>` | str |
| `NEWB_MODEL` | Override the Claude model id passed to the SDK. The CLI's `--model` flag wins when both are set. | `claude-haiku-4-5` | str |
| `NEWB_PIP_CACHE_DIR` | Host directory mounted into the container as the agent's `~/.cache/pip`. Local-dev escape hatch — leave unset for CI (cold install is the honest test). | unset | path |

## Hardening (configurable, opt-in)

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `NEWB_HARDEN_CAP_DROP_ALL` | Drop all Linux kernel capabilities. | `1` | bool |
| `NEWB_HARDEN_NO_NEW_PRIVS` | Block setuid privilege escalation. | `1` | bool |
| `NEWB_HARDEN_NO_NETWORK` | If 1, `--network=none` (breaks pip + SDK). | `0` | bool |
| `NEWB_HARDEN_MEMORY` | Container memory cap (e.g. `4g`). | unlimited | str |
| `NEWB_HARDEN_CPUS` | Container CPU cap (cores). | unlimited | str |
| `NEWB_HARDEN_PIDS_LIMIT` | Container PID cap. | unlimited | int |
| `NEWB_HARDEN_TMPFS_NOEXEC` | Mount `/tmp` with `noexec,nosuid`. | `0` | bool |

CLI flags (`--harden-memory`, `--harden-cpus`, …) override these.

## Meta (env-loader)

| Variable | Purpose |
|---|---|
| `NEWB_ENV_SRC` | Path to a `.src` file (or directory of `.src` files) sourced at startup. Generate a template with `newb env-template -o ~/.config/newb/local.src`. |

## SDK-internal (set by the host runner, read by `containers/runner.py`)

| Variable | Purpose | Default |
|---|---|---|
| `NEWB_CWD` | Working directory the SDK uses inside the container. | `/work/project` |
| `NEWB_SKILLS_PATH` | Absolute path inside the container of the focused docs subdir; interpolated into prompts via `{skills_path}`. | `/work/project` |
| `NEWB_SCOPE` | `all` (full agentic, `bypassPermissions`) or `docs` (read-only audit, `acceptEdits` + `Read/Glob/Grep` allowlist). | `all` |
| `NEWB_MCP_SERVERS_JSON` | JSON-encoded `mcp_servers` table — produced from `[tool.newb] mcp_servers` and decoded by `containers/runner.py` for `ClaudeAgentOptions(mcp_servers=...)`. | unset |

These are produced by the host runner and consumed by the
in-container `runner.py`. Users don't normally set them.

## What newb does NOT read

- `ANTHROPIC_API_KEY` (upstream — actively masked when running).
- `CLAUDE_API_KEY`, `OPENAI_API_KEY`, etc. — newb is Claude-only.
- `SCITEX_*` — newb is `external-lib` (like figrecipe / socialia),
  not under the `scitex.<module>` umbrella; uses its own `NEWB_`
  namespace.
