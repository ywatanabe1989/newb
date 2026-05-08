# newb runtime container — runs the claude-agent-sdk against a mounted
# project root. Container = the real isolation boundary; SDK options
# inside grant the agent FULL agentic permissions (Read + Write + Edit
# + Bash + Glob + Grep + acceptEdits) so it can actually try the
# package: pip install -e ., python -c "import pkg", <pkg> --help.
#
# Build:
#   docker build -t ghcr.io/ywatanabe1989/newb-runner:VERSION containers/
#
# Run (manual):
#   docker run --rm \
#     -v <staged-project>:/work/project \
#     -e NEWB_ANTHROPIC_API_KEY \
#     ghcr.io/ywatanabe1989/newb-runner:VERSION \
#     "<prompt>"
#
# newb's DockerRunner does this automatically (and stages the project
# root respecting .gitignore via `git ls-files`).

FROM python:3.11-slim

# Minimal: claude-agent-sdk bundles its own self-contained CLI binary
# (~237MB ELF, no Node needed). Add:
# * `ca-certificates` for HTTPS to api.anthropic.com
# * `git`             so newb can pass git-URL sources + so packages
#                     using setuptools_scm can resolve their version
#                     when the agent runs `pip install -e .`
# * `build-essential` so `pip install -e .` succeeds for packages
#                     with optional C extensions (best-effort)
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install the SDK (unpinned floor). The 0.1.73-0.1.77 "regression"
# we suspected at 0.26.0 was actually the OAuth-bare-env auth bug
# in disguise — fixed by 0.26.2's credentials.json bind-mount path.
# Verified locally on 2026-05-08 that 0.1.77 round-trips a real SDK
# query() in 5s with a bind-mounted credentials.json, no
# "is_error=True / subtype=success" failure.
RUN pip install --no-cache-dir 'claude-agent-sdk>=0.1.0'

# Bake the runner script into the image so newb only mounts the project.
COPY runner.py /opt/newb/runner.py

# The agent's CWD inside the container; the project is bind-mounted here.
WORKDIR /work

# Default to non-root for hardening. NEWB_ANTHROPIC_API_KEY is passed via -e.
# The agent needs write access to /work/project for `pip install -e .`,
# so make the staged copy owned by the runtime user.
RUN useradd -m -u 1000 newb \
    && mkdir -p /work /home/newb/.claude \
    && chown -R newb:newb /work /home/newb
# Pre-creating /home/newb/.claude/ owned by `newb` matters: when the
# host bind-mounts ~/.claude/.credentials.json into the container,
# Docker would otherwise create the parent dir as root, blocking the
# SDK from writing /home/newb/.claude/session-env at runtime.
USER newb

ENTRYPOINT ["python", "/opt/newb/runner.py"]
