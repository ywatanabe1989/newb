---
name: newb-isolation-runtimes
description: The three isolation runtimes (host/docker/apptainer), what each fences off, and why setting_sources=[]+allowed_tools=["Read"]+cwd=staged is the safety floor across all three.
tags: [newb, scitex-package]
---

# Isolation runtimes (`--runtime`)

Selects where the `claude-agent-sdk` query runs. All three apply the
same SDK-level fences (`setting_sources=[]`, `allowed_tools=["Read"]`,
`cwd=<staged copy>`); they differ in whether the **filesystem and
network** the agent sees are also fenced off.

| Value | Where the agent runs | FS fence | Net fence | Speed | Backend |
|---|---|---|---|---|---|
| `host` (default) | host subprocess via the SDK | **soft** — Read tool can technically reach host fs | **none** | ~10-15 s/q | `_sdk_runner.SdkRunner` |
| `docker` | inside `ghcr.io/ywatanabe1989/newb-runner` container | **hard** — only `<staged>:ro` mounted | bridged | ~15-20 s/q (after image pull) | `_container_runner.DockerRunner` |
| `apptainer` | same image via `apptainer run docker://...` | **hard** — `--no-home --containall` + bind | rootless | ~20-30 s/q | `_container_runner.ApptainerRunner` |

## What's fenced (all runtimes)

| Fence | Mechanism | Why |
|---|---|---|
| Skip host CLAUDE.md / .claude/ settings | `setting_sources=[]` | Local agent config could leak topic-specific instructions or tools the package's docs don't actually expose. |
| Read-only tool surface | `allowed_tools=["Read"]` | No Bash, no Write, no WebFetch — the agent can ONLY read .md files in the staged dir. Removes hallucination through tool execution. |
| Working directory = staged copy | `cwd=<tmp>/<pkg>/` | The skills source is `shutil.copytree`'d to a tmp dir before each run; the agent's filesystem horizon is exactly the package's docs. |
| Bounded turns | `max_turns=8` | Answering should need 1-3 Reads; >8 indicates docs scattered enough that the agent gives up. |

## Why both `host` and the containers exist

`host` is fast (no image pull, no docker daemon round-trip). It's
sufficient when the staged dir contains only the package's own docs —
which is the common case.

`docker` / `apptainer` add a real filesystem boundary so the Read tool
**cannot** reach the host even in principle, even if a future SDK
release relaxed the cwd constraint. Use them when:

- Verifying a third-party repo cloned from a URL
- Running in CI on a shared runner
- Running on HPC where docker isn't allowed (use `apptainer`)

## Container image

`ghcr.io/ywatanabe1989/newb-runner:<VERSION>` — built from
`containers/Dockerfile` in the repo, published by
`.github/workflows/publish-image.yml`.

Override:

```bash
NEWB_DOCKER_IMAGE=ghcr.io/me/my-fork:latest newb ./skills --runtime docker
```

## Auth pass-through

Container runtimes require `NEWB_ANTHROPIC_API_KEY` to be set on the
host — they read that NEWB_-prefixed var and forward it to the
container as `ANTHROPIC_API_KEY` (`-e` for docker, `--env` for
apptainer) so the SDK inside the container can pick it up. newb never
reads the upstream `ANTHROPIC_API_KEY` directly.

The `host` runtime additionally accepts `~/.claude/` OAuth (the SDK's
bundled CLI inherits it on personal machines) when
`NEWB_ANTHROPIC_API_KEY` is unset; in that case newb actively masks
any stray `ANTHROPIC_API_KEY` for the duration of the call so it
can't sneak in.
