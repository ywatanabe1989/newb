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

## Auth (one of these — opt-in)

| Variable | Purpose | Default | Type |
|---|---|---|---|
| `NEWB_ANTHROPIC_API_KEY` | Canonical Claude API key (`sk-ant-api03-…`). Forwarded to the container as `ANTHROPIC_API_KEY`. | unset | secret |
| `NEWB_ANTHROPIC_API_KEY_OAUTH` | Claude Code subscription token (`sk-ant-oat01-…`) for Pro / Max users. Extract from `~/.claude/.credentials.json` via `jq -r .claudeAiOauth.accessToken`. Same forwarding. | unset | secret |

If both are set, `NEWB_ANTHROPIC_API_KEY` wins.

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
