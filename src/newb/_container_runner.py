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

DEFAULT_IMAGE = "ghcr.io/ywatanabe1989/newb-runner:latest"
DEFAULT_TIMEOUT_S = 240


class _BaseContainerRunner:
    """Common: stage skills under a tmp dir, exec via subprocess, capture stdout."""

    runtime_bin: str = ""  # "docker" or "apptainer" — set by subclass

    def __init__(
        self,
        *,
        skills_mount: Path,
        model: str = "claude-haiku-4-5",
        image: str | None = None,
    ):
        if not shutil.which(self.runtime_bin):
            raise RuntimeError(
                f"{type(self).__name__} requires `{self.runtime_bin}` on PATH."
            )
        api_key = os.environ.get("NEWB_ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"{type(self).__name__} needs $NEWB_ANTHROPIC_API_KEY set "
                "(forwarded to the container as ANTHROPIC_API_KEY for the SDK). "
                "newb never reads the upstream ANTHROPIC_API_KEY env var — "
                "set NEWB_ANTHROPIC_API_KEY explicitly to opt in."
            )
        self._api_key = api_key
        self.skills_mount = Path(skills_mount).resolve()
        self.model = model
        self.image = image or os.environ.get("NEWB_DOCKER_IMAGE") or DEFAULT_IMAGE
        # Stage a clean read-only copy so the container can't see anything
        # outside the package's skills.
        self._stage_dir = Path(tempfile.mkdtemp(prefix="newb-stage-"))
        target = self._stage_dir / "skills"
        shutil.copytree(self.skills_mount, target)
        self.skills_path = "/work/skills"

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
        skills_host = str(self._stage_dir / "skills")
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "bridge",
            "-v",
            f"{skills_host}:/work/skills:ro",
            "-e",
            f"ANTHROPIC_API_KEY={self._api_key}",
            "-e",
            f"NEWB_MODEL={self.model}",
            self.image,
            prompt,
        ]


class ApptainerRunner(_BaseContainerRunner):
    """Runs the SDK call inside an apptainer/singularity container.

    Uses ``apptainer run docker://<image>`` which auto-pulls + caches
    the OCI image as a SIF. Suitable for HPC contexts where docker is
    not available.
    """

    runtime_bin = "apptainer"

    def _build_argv(self, prompt: str) -> list[str]:
        skills_host = str(self._stage_dir / "skills")
        # apptainer's --bind format is host:container[:ro]
        # Note: env vars go via SINGULARITYENV_* / APPTAINERENV_* prefix.
        env = os.environ.copy()
        env["APPTAINERENV_ANTHROPIC_API_KEY"] = self._api_key
        env["APPTAINERENV_NEWB_MODEL"] = self.model
        # We can't return env from _build_argv; subclass's run() needs to
        # override. Simpler: use --env on the apptainer cmdline.
        return [
            "apptainer",
            "run",
            "--no-home",
            "--containall",
            "--bind",
            f"{skills_host}:/work/skills:ro",
            "--env",
            f"ANTHROPIC_API_KEY={self._api_key}",
            "--env",
            f"NEWB_MODEL={self.model}",
            f"docker://{self.image}",
            prompt,
        ]
