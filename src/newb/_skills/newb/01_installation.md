---
description: |
  [TOPIC] Installation
  [DETAILS] pip install newb. Requires `claude-agent-sdk` + a container runtime (docker default, podman rootless, apptainer for HPC). Set NEWB_ANTHROPIC_API_KEY.
tags: [newb-installation]
---

# Installation

## Standard

```bash
pip install newb
```

Pulls `claude-agent-sdk` + click + pyyaml. You also need:

| Requirement                  | Why                                          |
|------------------------------|----------------------------------------------|
| A container runtime          | newb runs the agent inside a container       |
| `NEWB_ANTHROPIC_API_KEY`     | Anthropic key the SDK uses inside the container |

## Container runtime

Pick one (newb auto-detects in this order):

| Runtime    | Install                                  | Notes                       |
|------------|------------------------------------------|-----------------------------|
| docker     | https://docs.docker.com/get-docker/      | Default                     |
| podman     | `apt install podman` / `brew install podman` | Rootless                |
| apptainer  | https://apptainer.org/                   | HPC                         |

The removed `host` runtime is intentional — full agentic permissions on
the host are unsafe.

## Auth

```bash
export NEWB_ANTHROPIC_API_KEY=sk-ant-...
```

newb reads ONLY this var (no surprise from a stray `ANTHROPIC_API_KEY`).
The runtime forwards it as `ANTHROPIC_API_KEY` inside the container.

## Verify

```bash
newb --version
newb --help
python -c "import newb; print(newb.__version__)"
docker --version          # or `podman --version` / `apptainer --version`
```

## Editable install (development)

```bash
git clone https://github.com/ywatanabe1989/newb
cd newb
pip install -e .
```
