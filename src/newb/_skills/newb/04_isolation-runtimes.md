---
name: newb-isolation-runtimes
description: The two container isolation runtimes (docker default, apptainer for HPC), what each fences off, and the design rule "container is the boundary, not the SDK options" — full agentic permissions inside, dropping the unsafe host runtime in 0.9.
tags: [newb, scitex-package]
---

# Isolation runtimes (`--runtime`)

Selects the container the `claude-agent-sdk` query runs in. The
container — its filesystem and network namespace — is the real
isolation boundary. Inside the container the agent gets **full
agentic permissions** (Read + Write + Edit + Bash + Glob + Grep +
`permission_mode=acceptEdits`) so it can actually try the package the
way a real new user would.

| Value | Where the agent runs | FS fence | Net fence | Speed | Backend |
|---|---|---|---|---|---|
| `docker` *(default)* | `ghcr.io/ywatanabe1989/newb-runner` container | **hard** — only the staged project root is bind-mounted | bridged | ~15-30 s/q (after image pull) | `_container_runner.DockerRunner` |
| `apptainer` | same image via `apptainer run docker://…` | **hard** — `--no-home --containall` + bind | rootless | ~20-40 s/q | `_container_runner.ApptainerRunner` |

## Container is the boundary, not the SDK options

Earlier newb (0.7-0.8) gave the SDK `allowed_tools=["Read"]` even
inside docker — belt-and-suspenders for an environment that already
has no host paths. That was a false sense of security AND it crippled
the agent: it couldn't `pip install -e .`, couldn't `python -c
"import pkg"`, couldn't run `<pkg> --help`. It could only read
markdown.

newb 0.9 separated the layers:

```
┌─────────────────────────────────────────────┐
│ Container layer  (REAL boundary)            │
│  - filesystem isolation (only staged)       │
│  - network isolation (--network=bridge)     │
│  - process isolation (PID namespace)        │
│  - destroyed after run                      │
└─────────────────────────────────────────────┘
       ↓  inside, agent has full power
┌─────────────────────────────────────────────┐
│ SDK layer  (agent BEHAVIOR)                 │
│  - allowed_tools=["Read","Write","Edit",    │
│                   "Bash","Glob","Grep"]     │
│  - permission_mode="acceptEdits"            │
│  - setting_sources=[]   (no host CLAUDE.md) │
│  - max_turns=15                             │
└─────────────────────────────────────────────┘
       ↓  agent does its thing
┌─────────────────────────────────────────────┐
│ Agent  (the newbie)                         │
│  - reads README, src/, _skills/             │
│  - runs pip install, imports, CLI tests     │
│  - reports back what worked / what didn't   │
└─────────────────────────────────────────────┘
```

isolation = container, behavior = SDK, exploration = agent.

## Why the host runtime was dropped (0.9)

Full agentic permissions on the host are unsafe:

- agent could `rm -rf ~/proj/`, since cwd is a tmp dir but Bash can `cd`
- agent could `pip install` into the global env
- "container is the boundary" only holds when there IS a container

The clear separation is now: `docker` (and `apptainer`) for *real*
agentic verification; nothing for "soft" host-side runs. Use a
container — the image is small and pre-pulled in CI.

## Auth pass-through

Both runtimes require `NEWB_ANTHROPIC_API_KEY` on the host —
forwarded to the container as `ANTHROPIC_API_KEY` (`-e` for docker,
`--env` for apptainer) so the SDK inside picks it up. newb never
reads the upstream `ANTHROPIC_API_KEY` directly — opt in explicitly.

## Image override

```bash
NEWB_DOCKER_IMAGE=ghcr.io/me/my-fork:latest newb . --runtime docker
```

The image is published from `containers/Dockerfile` via
`.github/workflows/publish-image.yml`.
