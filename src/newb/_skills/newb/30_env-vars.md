---
name: newb-env-vars
description: Environment variables read by newb at import / runtime. NEWB_-prefixed only — never silently inherits the upstream ANTHROPIC_API_KEY. Documents auth (API key + OAuth Pro/Max), runtime (docker image, model), and SDK-internal (cwd, skills path) vars.
tags: [newb, scitex-package]
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
| `NEWB_DOCKER_IMAGE` | Override the container image used by `--runtime docker` / `apptainer`. | `ghcr.io/ywatanabe1989/newb-runner:latest` | str |
| `NEWB_MODEL` | Override the Claude model id passed to the SDK. The CLI's `--model` flag wins when both are set. | `claude-haiku-4-5` | str |

## SDK-internal (set by the runner, read by `containers/runner.py`)

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `NEWB_CWD` | Working directory the SDK uses inside the container. | `/work/project` | path |
| `NEWB_SKILLS_PATH` | Absolute path inside the container of the focused docs subdir; interpolated into prompts via `{skills_path}`. | `/work/project` | path |

These two are produced by `_container_runner.DockerRunner` /
`ApptainerRunner` and consumed by the in-container `runner.py`. Users
don't normally set them.

## What newb does NOT read

- `ANTHROPIC_API_KEY` (upstream — actively masked when running).
- `CLAUDE_API_KEY`, `OPENAI_API_KEY`, etc. — newb is Claude-only.
- `SCITEX_*` — newb is `external-lib` (like figrecipe / socialia),
  not under the `scitex.<module>` umbrella; uses its own `NEWB_`
  namespace.
