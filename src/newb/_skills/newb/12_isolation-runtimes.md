---
description: |
  [TOPIC] Isolation Runtimes
  [DETAILS] The three container isolation runtimes (docker default, podman rootless, apptainer HPC), one-container-per-run batched execution, the design rule "container is the boundary, not the SDK options", permission_mode=bypassPermissions inside the container, and configurable hardening.
tags: [newb-isolation-runtimes]
---

# Isolation runtimes (`--runtime`)

Selects the container backend the `claude-agent-sdk` query batch runs
in. The container — its filesystem and network namespace — is the
real isolation boundary. Inside the container the agent gets **full
agentic permissions** (Read + Write + Edit + Bash + Glob + Grep +
`permission_mode="bypassPermissions"` for `--scope all`) so it can
actually try the package the way a real new user would.

| Value | Where the agent runs | FS fence | Net fence | Backend |
|---|---|---|---|---|
| `docker` *(default)* | `ghcr.io/ywatanabe1989/newb-runner` container | **hard** — only the staged project root is bind-mounted | bridged | `_container_runner.DockerRunner` |
| `podman` | same image, rootless | **hard** | bridged | `_container_runner.PodmanRunner` |
| `apptainer` | `apptainer run docker://…` | **hard** — `--no-home --containall` + bind | rootless | `_container_runner.ApptainerRunner` |

## One container per run

All prompts run in a single container:

- The host runner builds a JSON envelope `{"prompts": [...]}` and
  pipes it to the container on stdin.
- The in-container runner loops each prompt as an independent
  `query()` so conversation context never leaks between answers.
- On-disk state — including `pip install -e .` from
  `post_install_check` — persists across prompts because the
  container's filesystem persists across the per-prompt `query()`
  calls.
- The container emits a JSON envelope `{"results": [...]}` on stdout.

This makes `post_install_check` actually meaningful: the install
state it produces is visible to subsequent questions.

### Two architectural invariants (verified empirically 2026-05-02)

Both invariants were probed by piping a 2-prompt JSON envelope
directly to the container runner:

1. **Filesystem state persists across prompts.** Prompt 1 ran
   `pip install --user six` and wrote `/tmp/marker.txt`. Prompt 2 — an
   independent `query()` with a fresh agent — successfully read the
   marker content back AND `import six` (1.17.0).
2. **Conversation context does NOT leak across prompts.** Prompt 1
   was told a secret word and asked to acknowledge with `OK`. Prompt 2
   asked "what was the secret word?" and the agent correctly replied
   `NO_MEMORY` because the previous conversation history wasn't
   carried over.

Together: install in q5 → import in q6 works; answers in q5 → bias in
q6 does not.

**The agent lives long within one run, not across runs.** Container
is `--rm`'d at the end; every `newb` invocation is a cold start. The
`--pip-cache` mount carries wheel downloads forward but install state
itself does not. If you need cross-run state, that's outside newb's
scope — newb is a one-shot newbie probe by design.

## Container is the boundary, not the SDK options

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
│  - permission_mode="bypassPermissions"      │
│      (scope=all, the default)               │
│  - permission_mode="acceptEdits" +          │
│    allowed_tools=["Read","Glob","Grep"]     │
│      (scope=docs, read-only audit)          │
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

## Why `bypassPermissions` inside the container

`permission_mode="acceptEdits"` only auto-approves edits — `Bash`
calls (`pip install -e .`, `python -c "import pkg"`,
`<pkg> --help`) hit a permission prompt and deadlock the
non-interactive runner. `--scope all` uses
`bypassPermissions` (the SDK equivalent of
`--dangerously-skip-permissions`). Safe because the container is
the boundary, single-shot, and the staged project is the agent's
whole filesystem horizon.

`--scope docs` keeps `acceptEdits` + `allowed_tools=["Read","Glob","Grep"]`
so it can scan the project but not modify it or shell out.

## Hardening (configurable)

Defaults are boundary-only: `--cap-drop=ALL`, `--security-opt=no-new-privileges`,
bridge network. Resource caps (memory, CPU, PIDs, tmpfs noexec)
default to **unlimited** so the agent can actually exercise the
package. Opt in via CLI flag or `NEWB_HARDEN_*` env var:

```bash
newb . --harden-memory 4g --harden-cpus 2 --harden-pids-limit 256
NEWB_HARDEN_MEMORY=4g NEWB_HARDEN_CPUS=2 newb .
```

Layers: CLI flag > `NEWB_HARDEN_*` env var > built-in default.

## Pip cache (local-dev escape hatch)

```bash
newb . --pip-cache ~/.cache/newb-pip
NEWB_PIP_CACHE_DIR=~/.cache/newb-pip newb .
```

Mounted into the container as `/home/newb/.cache/pip`. **Leave unset
for CI** — cold install is the honest newbie test, and a warm cache
would hide "package can't be installed from scratch" failures.

## Auth pass-through

All runtimes require `NEWB_ANTHROPIC_API_KEY` on the host. Forwarded
into the container (`-e` for docker/podman, `--env` for apptainer);
the in-container runner promotes it to `ANTHROPIC_API_KEY` for the
bundled CLI. The Anthropic backend accepts API keys
(`sk-ant-api03-…`) and OAuth access tokens (`sk-ant-oat01-…`) on the
same Authorization header — newb does not dispatch on prefix.

## Image override

```bash
NEWB_DOCKER_IMAGE=ghcr.io/me/my-fork:latest newb . --runtime docker
```

Default tag is pinned to `:<newb-version>` so a stale local
`:latest` from an earlier newb install can never silently mismatch
the host code. Image is published from `containers/Dockerfile` via
`.github/workflows/publish-image.yml`.
