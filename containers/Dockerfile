# newb runtime container — runs the claude-agent-sdk against a mounted
# skills directory, in real isolation (the agent's Read tool can only
# touch what's mounted).
#
# Build:
#   docker build -t ghcr.io/ywatanabe1989/newb-runner:VERSION containers/
#
# Run (manual):
#   docker run --rm \
#     -v <staged>:/work/skills:ro \
#     -e ANTHROPIC_API_KEY \
#     ghcr.io/ywatanabe1989/newb-runner:VERSION \
#     python /opt/newb/runner.py "<prompt>"
#
# newb's DockerRunner does this automatically.

FROM python:3.11-slim

# Minimal: claude-agent-sdk bundles its own self-contained CLI binary
# (~237MB ELF, no Node needed). Add only:
# * `ca-certificates` for HTTPS to api.anthropic.com
# * `git` so newb can pass git-URL sources straight through
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install the SDK. Pin a floor version so behavior matches the host
# newb that spawned the container.
RUN pip install --no-cache-dir 'claude-agent-sdk>=0.1.0'

# Bake the runner script into the image so newb only mounts the skills.
COPY runner.py /opt/newb/runner.py

# The agent's CWD inside the container — only the skills get mounted here.
WORKDIR /work

# Default to non-root for hardening. ANTHROPIC_API_KEY is passed via -e.
RUN useradd -m -u 1000 newb
USER newb

ENTRYPOINT ["python", "/opt/newb/runner.py"]
