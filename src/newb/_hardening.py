# ---
# Timestamp: 2026-05-02
# Author: ywatanabe
# File: src/newb/_hardening.py
# ---

"""Container hardening flags for DockerRunner / ApptainerRunner.

Design rule:

- Container = isolation boundary.
- Agent runs *unconstrained by default* inside, so it can actually
  exercise the package (newb's core value).
- Hardening flags are *opt-in knobs* the user can dial up via the CLI
  or library kwargs. Defaults harden the boundary edge only; resource
  limits and write/exec restrictions stay off so the agent can install
  + run + test the target package.

Default flags (always on, no agent impact):

- ``--cap-drop=ALL`` — drops Linux kernel capabilities (NET_ADMIN,
  SYS_PTRACE, etc.) that the agent never needs.
- ``--security-opt=no-new-privileges`` — blocks setuid escalation.
- ``--network=bridge`` — required so the SDK can reach
  api.anthropic.com and pip can reach pypi.org.

Optional knobs (off by default; pass to enable):

- ``memory``, ``cpus``, ``pids_limit`` — resource caps. Off by default
  because they break packages needing >2 GB installs, parallel pytest,
  fork-heavy build tools.
- ``tmpfs_noexec=True`` — adds ``/tmp:rw,noexec,nosuid``. Off by default
  because pip and pytest sometimes write+exec wheels in /tmp.
- ``no_network=True`` — replaces ``--network=bridge`` with
  ``--network=none``. Breaks pip and the SDK; only useful in a fully
  offline workflow.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else None


def _env_int(name: str) -> int | None:
    v = _env_str(name)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


@dataclass
class HardeningOptions:
    """User-tunable hardening knobs.

    Resolution order (highest precedence first):

    1. Explicit kwargs / CLI flags
    2. ``NEWB_HARDEN_*`` env vars
    3. Defaults (boundary-only hardening; agent unconstrained)

    Env var ↔ field mapping:

    | Env var                       | Field             |
    |-------------------------------|-------------------|
    | NEWB_HARDEN_CAP_DROP_ALL      | cap_drop_all      |
    | NEWB_HARDEN_NO_NEW_PRIVS      | no_new_privileges |
    | NEWB_HARDEN_NO_NETWORK        | no_network        |
    | NEWB_HARDEN_MEMORY            | memory            |
    | NEWB_HARDEN_MEMORY_SWAP       | memory_swap       |
    | NEWB_HARDEN_CPUS              | cpus              |
    | NEWB_HARDEN_PIDS_LIMIT        | pids_limit        |
    | NEWB_HARDEN_TMPFS_NOEXEC      | tmpfs_noexec      |
    """

    cap_drop_all: bool = True
    """Drop all Linux kernel capabilities. Safe to leave on."""

    no_new_privileges: bool = True
    """Block setuid privilege escalation. Safe to leave on."""

    no_network: bool = False
    """If True, ``--network=none`` (breaks pip + SDK)."""

    memory: str | None = None
    """e.g. ``'2g'``. None = unlimited (default)."""

    memory_swap: str | None = None
    """e.g. ``'2g'``. None = unlimited (default)."""

    cpus: str | None = None
    """e.g. ``'2'``. None = unlimited (default)."""

    pids_limit: int | None = None
    """e.g. 256. None = unlimited (default)."""

    tmpfs_noexec: bool = False
    """If True, mount ``/tmp:rw,noexec,nosuid``. Off by default — pip
    and pytest may need exec from /tmp."""

    @classmethod
    def from_env(cls) -> HardeningOptions:
        """Build from ``NEWB_HARDEN_*`` env vars, falling back to defaults."""
        return cls(
            cap_drop_all=_env_bool("NEWB_HARDEN_CAP_DROP_ALL", True),
            no_new_privileges=_env_bool("NEWB_HARDEN_NO_NEW_PRIVS", True),
            no_network=_env_bool("NEWB_HARDEN_NO_NETWORK", False),
            memory=_env_str("NEWB_HARDEN_MEMORY"),
            memory_swap=_env_str("NEWB_HARDEN_MEMORY_SWAP"),
            cpus=_env_str("NEWB_HARDEN_CPUS"),
            pids_limit=_env_int("NEWB_HARDEN_PIDS_LIMIT"),
            tmpfs_noexec=_env_bool("NEWB_HARDEN_TMPFS_NOEXEC", False),
        )

    def merged_with(self, **overrides) -> HardeningOptions:
        """Return a copy with ``overrides`` applied. Used by the CLI to
        layer ``--harden-*`` flags on top of env-var defaults. Values of
        ``None`` in ``overrides`` are ignored (so absent CLI flags
        don't clobber env-supplied values)."""
        merged = self.__dict__.copy()
        for k, v in overrides.items():
            if v is not None:
                merged[k] = v
        return HardeningOptions(**merged)


def hardening_argv(opts: HardeningOptions | None = None) -> list[str]:
    """Return the security-related Docker argv flags.

    Parameters
    ----------
    opts : HardeningOptions
        Knobs. ``None`` uses defaults (boundary-only hardening,
        agent unconstrained).

    Returns
    -------
    list[str]
        argv fragment to splice into the docker run invocation.
    """
    opts = opts or HardeningOptions()
    argv: list[str] = []

    if opts.cap_drop_all:
        argv.append("--cap-drop=ALL")
    if opts.no_new_privileges:
        argv.append("--security-opt=no-new-privileges")

    argv.append("--network=none" if opts.no_network else "--network=bridge")

    if opts.memory is not None:
        argv.append(f"--memory={opts.memory}")
    if opts.memory_swap is not None:
        argv.append(f"--memory-swap={opts.memory_swap}")
    if opts.cpus is not None:
        argv.append(f"--cpus={opts.cpus}")
    if opts.pids_limit is not None:
        argv.append(f"--pids-limit={opts.pids_limit}")
    if opts.tmpfs_noexec:
        argv += ["--tmpfs", "/tmp:rw,noexec,nosuid"]

    return argv


def apptainer_hardening_argv(opts: HardeningOptions | None = None) -> list[str]:
    """Apptainer-equivalent of ``hardening_argv``.

    Apptainer's flag set differs from docker's; not every docker flag
    has a direct apptainer counterpart. Best-effort parity for the
    subset that maps cleanly:

    - ``--memory`` (apptainer accepts the same value syntax: ``2g``).
    - ``--cpus``.
    - ``--pids-limit`` (cgroup-based, supported in modern apptainer).
    - ``--net --network none`` for ``no_network``. Default is the host
      network (apptainer's default; analog of docker's ``--network=bridge``).

    Not mapped (silent — caller should not assume parity):

    - ``--cap-drop=ALL`` — apptainer is rootless so capability drop is
      mostly moot; the underlying user namespace already restricts.
    - ``--security-opt=no-new-privileges`` — apptainer's security model
      handles privilege escalation via user namespaces, not this flag.
    - ``--tmpfs`` for /tmp — different syntax (``--no-mount tmp``); off
      by default to match docker behavior here.
    """
    opts = opts or HardeningOptions()
    argv: list[str] = []
    if opts.memory is not None:
        argv += ["--memory", str(opts.memory)]
    if opts.cpus is not None:
        argv += ["--cpus", str(opts.cpus)]
    if opts.pids_limit is not None:
        argv += ["--pids-limit", str(opts.pids_limit)]
    if opts.no_network:
        argv += ["--net", "--network", "none"]
    return argv


def hardening_summary(opts: HardeningOptions | None = None) -> dict:
    """Summary for the transparency report ``security:`` section."""
    opts = opts or HardeningOptions()
    return {
        "cap-drop": "ALL" if opts.cap_drop_all else "none",
        "no-new-privs": opts.no_new_privileges,
        "network": "none" if opts.no_network else "bridge",
        "memory-limit": opts.memory or "unlimited",
        "memory-swap": opts.memory_swap or "unlimited",
        "cpus-limit": opts.cpus or "unlimited",
        "pids-limit": opts.pids_limit or "unlimited",
        "tmpfs-noexec": opts.tmpfs_noexec,
    }


# EOF
