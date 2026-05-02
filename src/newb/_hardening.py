# ---
# Timestamp: 2026-05-02
# Author: ywatanabe
# File: src/newb/runtimes/_docker_hardening.py
# ---

"""Container hardening flags for DockerRunner._build_argv (Phase 1.5).

This is a *patch module* — apply by extending DockerRunner's argv builder
with `hardening_argv()`. Kept separate so the security flags are easy to
audit and toggle.

NOT included here:
- `--read-only` for the rootfs: would break `pip install -e .`. The agent
  needs to actually try the package, which is newb's core value.
- `--user 1000:1000`: the runner image already runs as a non-root user.
  Re-asserting it via --user can conflict with image USER directive on
  some Docker versions; left to image-side enforcement.

Trade-offs documented inline so a future maintainer doesn't tighten the
wrong knob and break the agent's ability to exercise the package.
"""

from __future__ import annotations


def hardening_argv(no_network: bool = False) -> list[str]:
    """Return the security-related Docker argv flags.

    Parameters
    ----------
    no_network : bool
        If True, fully isolate the container's network namespace
        (`--network=none`). This breaks `pip install` from PyPI and
        `claude-agent-sdk` calls to api.anthropic.com — only useful when
        combined with a pre-flight scan that has already done the
        evaluation, OR for fixture-based offline tests.

    Returns
    -------
    list[str]
        argv fragment to splice into the docker run invocation.
    """
    argv = [
        # Drop ALL Linux capabilities. The agent doesn't need any —
        # CAP_NET_BIND_SERVICE etc. are only relevant to processes that
        # bind privileged ports, which we don't.
        "--cap-drop=ALL",

        # Block setuid binaries and capability escalation in general.
        # If a malicious package tries to ship a setuid helper, this
        # neutralizes it.
        "--security-opt=no-new-privileges",

        # DoS containment. A runaway agent loop or a fork bomb in a
        # malicious package's setup.py won't take down the host.
        # Limits are deliberately generous: pip can pull large wheels,
        # tests may briefly spike memory.
        "--memory=2g",
        "--memory-swap=2g",  # disable swap escape from --memory
        "--cpus=2",
        "--pids-limit=256",  # raised from initial 100 — pip + pytest fork freely

        # /tmp must be writable for pip's build tree, but we don't need
        # to allow execution from it. noexec breaks one common malware
        # pattern (write-to-tmp, chmod, exec).
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=512m",
    ]

    if no_network:
        argv.append("--network=none")
    else:
        # Default. The SDK needs api.anthropic.com; pip needs PyPI.
        argv.append("--network=bridge")

    return argv


def hardening_summary(no_network: bool = False) -> dict[str, str | bool]:
    """Return a summary suitable for the transparency report header.

    The report renders this under `security:` so a Pharma audit reviewer
    can see at a glance which protections were active for a given run.
    """
    return {
        "cap-drop": "ALL",
        "no-new-privs": True,
        "memory-limit": "2g",
        "memory-swap": "2g",
        "cpus-limit": "2",
        "pids-limit": "256",
        "tmpfs": "/tmp (noexec,nosuid,512m)",
        "network": "none" if no_network else "bridge",
    }


# EOF
