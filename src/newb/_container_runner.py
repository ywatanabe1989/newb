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

from ._stage import stage_project

DEFAULT_IMAGE = "ghcr.io/ywatanabe1989/newb-runner:latest"
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
    ):
        if not shutil.which(self.runtime_bin):
            raise RuntimeError(
                f"{type(self).__name__} requires `{self.runtime_bin}` on PATH."
            )
        # Two opt-in env vars (NEWB_ prefix only — never silently picks
        # up the upstream ANTHROPIC_API_KEY):
        #   NEWB_ANTHROPIC_API_KEY        sk-ant-api03-...  (canonical)
        #   NEWB_ANTHROPIC_API_KEY_OAUTH  sk-ant-oat01-...  (Pro/Max
        #                                  users — extract from
        #                                  ~/.claude/.credentials.json)
        # Whichever is set gets forwarded to the container as
        # ANTHROPIC_API_KEY so the SDK inside picks it up.
        api_key = os.environ.get("NEWB_ANTHROPIC_API_KEY") or os.environ.get(
            "NEWB_ANTHROPIC_API_KEY_OAUTH"
        )
        if not api_key:
            raise RuntimeError(
                f"{type(self).__name__} needs $NEWB_ANTHROPIC_API_KEY "
                "(API key) or $NEWB_ANTHROPIC_API_KEY_OAUTH (Claude Code "
                "subscription, extracted from ~/.claude/.credentials.json) "
                "set. newb never reads the upstream ANTHROPIC_API_KEY env "
                "var — set the NEWB_-prefixed var explicitly to opt in."
            )
        self._api_key = api_key
        self.skills_mount = Path(skills_mount).resolve()
        self.project_root = (
            Path(project_root).resolve() if project_root else self.skills_mount
        )
        self.model = model
        self.image = image or os.environ.get("NEWB_DOCKER_IMAGE") or DEFAULT_IMAGE
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
        # NOTE: bind-mount is read-write (no `:ro`) so the agent can
        # `pip install -e .` and write small example files. The staged
        # dir is a tmp copy that gets rmtree'd after the run, so the
        # user's source is untouched.
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "bridge",
            "-v",
            f"{project_host}:/work/project",
            "-e",
            f"ANTHROPIC_API_KEY={self._api_key}",
            "-e",
            f"NEWB_MODEL={self.model}",
            "-e",
            f"NEWB_SKILLS_PATH={self.skills_path}",
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
        project_host = str(self._stage_target)
        # bind-mount is read-write (default — no `:ro`) so the agent
        # can `pip install -e .` and write small example files inside.
        # The staged dir is tmp; user's source is untouched.
        return [
            "apptainer",
            "run",
            "--no-home",
            "--containall",
            "--bind",
            f"{project_host}:/work/project",
            "--env",
            f"ANTHROPIC_API_KEY={self._api_key}",
            "--env",
            f"NEWB_MODEL={self.model}",
            "--env",
            f"NEWB_SKILLS_PATH={self.skills_path}",
            f"docker://{self.image}",
            prompt,
        ]
