"""Container-backed runners — docker / apptainer.

Same wire contract as ``SdkRunner`` (sync ``.run(prompt) -> {"result": text}``)
but the SDK call happens inside a container so the agent's filesystem
horizon is the staged skills mount and nothing else. Real isolation,
unlike the host-subprocess SdkRunner whose Read tool can theoretically
walk the host filesystem.

Image: ``ghcr.io/ywatanabe1989/newb-runner:<VERSION>`` (built from
``containers/Dockerfile`` in this repo). Override via env::

    NEWB_DOCKER_IMAGE=ghcr.io/me/my-fork:latest newb ./skills --runtime docker
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ._hardening import HardeningOptions, hardening_argv
from ._stage import stage_project


def _default_image() -> str:
    """Pin the container image tag to *this* newb's version.

    Returns ``ghcr.io/ywatanabe1989/newb-runner:<newb-version>``. This
    means a stale local ``:latest`` from an earlier newb install can
    never silently mismatch the host code (e.g. host expects
    /work/project but the cached image still has /work/skills).

    Override with ``NEWB_DOCKER_IMAGE=...`` for forks / dev images.
    """
    try:
        from newb import __version__ as _v
    except Exception:
        _v = "latest"
    return f"ghcr.io/ywatanabe1989/newb-runner:{_v}"


DEFAULT_TIMEOUT_S = 240


class _BaseContainerRunner:
    """Common: stage the project root under a tmp dir, exec via subprocess, capture stdout.

    The container itself is the hard boundary — only the staged project
    root is bind-mounted read-only. Inside the container, the agent
    sees the full package context (README, src/, tests/, _skills/,
    examples/, ...) at /work/project, with the focused docs dir at
    /work/project/<skills-relpath>.
    """

    runtime_bin: str = ""  # "docker" or "apptainer" — set by subclass

    def __init__(
        self,
        *,
        skills_mount: Path,
        project_root: Path | None = None,
        model: str = "claude-haiku-4-5",
        image: str | None = None,
        hardening: HardeningOptions | None = None,
        scope: str = "all",
    ):
        if not shutil.which(self.runtime_bin):
            raise RuntimeError(
                f"{type(self).__name__} requires `{self.runtime_bin}` on PATH."
            )
        # Hardening defaults: boundary-only (cap-drop=ALL, no-new-privs,
        # bridge network). Resource caps stay off so the agent can
        # actually exercise the package. CLI / library callers can pass
        # ``hardening=HardeningOptions(...)`` to opt in to stricter caps,
        # or set ``NEWB_HARDEN_*`` env vars (read via from_env).
        self.hardening = hardening or HardeningOptions.from_env()
        # ONE opt-in env var (NEWB_ prefix only — never silently picks
        # up the upstream ANTHROPIC_API_KEY). The value is opaque from
        # newb's POV: container's runner.py decides whether it's a
        # real API key (sk-ant-api*) or a Claude Code OAuth token
        # (sk-ant-oat*) by prefix.
        api_key = os.environ.get("NEWB_ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"{type(self).__name__} needs $NEWB_ANTHROPIC_API_KEY set. "
                "newb never reads the upstream ANTHROPIC_API_KEY env var — "
                "set the NEWB_-prefixed var explicitly to opt in."
            )
        self._api_key = api_key
        self.scope = scope if scope in {"all", "docs"} else "all"
        self.skills_mount = Path(skills_mount).resolve()
        self.project_root = (
            Path(project_root).resolve() if project_root else self.skills_mount
        )
        self.model = model
        self.image = image or os.environ.get("NEWB_DOCKER_IMAGE") or _default_image()
        # Stage the whole project root (with cache/build/venv ignored).
        # The container mounts this read-only as /work/project so the
        # agent has the full post-install package shape — README,
        # src/, tests/, _skills/, examples/.
        self._stage_dir = Path(tempfile.mkdtemp(prefix="newb-stage-"))
        target = self._stage_dir / "project"
        stage_project(self.project_root, target)
        self._stage_target = target
        try:
            rel = self.skills_mount.relative_to(self.project_root)
            self.skills_path = f"/work/project/{rel.as_posix()}"
        except ValueError:
            self.skills_path = "/work/project"

    def _build_argv(self, prompt: str) -> list[str]:
        raise NotImplementedError

    def run(
        self, prompt: str, *, model: str | None = None, timeout: int = DEFAULT_TIMEOUT_S
    ) -> dict:
        argv = self._build_argv(prompt)
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"result": f"(container timeout after {timeout}s)"}
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:500]
            raise RuntimeError(
                f"{self.runtime_bin} runner failed (rc={proc.returncode}): {err}"
            )
        return {"result": proc.stdout.strip() or "(empty response)"}

    def close(self) -> None:
        if self._stage_dir.exists():
            shutil.rmtree(self._stage_dir, ignore_errors=True)


class DockerRunner(_BaseContainerRunner):
    """Runs the SDK call inside a docker container."""

    runtime_bin = "docker"

    def _build_argv(self, prompt: str) -> list[str]:
        project_host = str(self._stage_target)
        # Forward NEWB_ANTHROPIC_API_KEY into the container; the
        # in-container runner.py promotes it to ANTHROPIC_API_KEY for
        # the bundled CLI. The Anthropic backend accepts both real
        # API keys (sk-ant-api*) and Claude Code OAuth access tokens
        # (sk-ant-oat*) on the same code path — no host-side dispatch
        # needed.
        argv = ["docker", "run", "--rm"]
        argv += hardening_argv(self.hardening)
        argv += [
            "-v",
            f"{project_host}:/work/project",
            "-e",
            f"NEWB_ANTHROPIC_API_KEY={self._api_key}",
            "-e",
            f"NEWB_MODEL={self.model}",
            "-e",
            f"NEWB_SKILLS_PATH={self.skills_path}",
            "-e",
            f"NEWB_SCOPE={self.scope}",
            self.image,
            prompt,
        ]
        return argv


class PodmanRunner(DockerRunner):
    """Drop-in podman replacement for ``DockerRunner``.

    Podman's ``run`` subcommand is argv-compatible with docker's
    (cap-drop, security-opt, network, memory, cpus, pids-limit, tmpfs,
    -v, -e — all behave the same). Swap only the leading binary name;
    everything else inherits from ``DockerRunner``.

    Use cases: rootless container without a docker daemon, RHEL/Fedora
    hosts, or environments where docker isn't installed but podman is.
    """

    runtime_bin = "podman"

    def _build_argv(self, prompt: str) -> list[str]:
        argv = super()._build_argv(prompt)
        # First element is "docker"; replace with "podman".
        argv[0] = "podman"
        return argv


class ApptainerRunner(_BaseContainerRunner):
    """Runs the SDK call inside an apptainer/singularity container.

    Uses ``apptainer run docker://<image>`` which auto-pulls + caches
    the OCI image as a SIF. Suitable for HPC contexts where docker is
    not available.
    """

    runtime_bin = "apptainer"

    def _build_argv(self, prompt: str) -> list[str]:
        project_host = str(self._stage_target)
        return [
            "apptainer",
            "run",
            "--no-home",
            "--containall",
            "--bind",
            f"{project_host}:/work/project",
            "--env",
            f"NEWB_ANTHROPIC_API_KEY={self._api_key}",
            "--env",
            f"NEWB_MODEL={self.model}",
            "--env",
            f"NEWB_SKILLS_PATH={self.skills_path}",
            "--env",
            f"NEWB_SCOPE={self.scope}",
            f"docker://{self.image}",
            prompt,
        ]
