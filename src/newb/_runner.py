"""Docker harness for running ``claude -p`` against a scoped skills mount.

Lifted from scitex-dev's ``_agentic_testing/_core.py`` and decoupled from
the SciTeX ecosystem (no ECOSYSTEM registry, no host-runner pool — just
the docker runner that ``newb verify`` needs).

Empirically validated 2026-04-23 (in scitex-dev):
    - 2.3-3.3 s / call on Haiku
    - $0.003-$0.010 per "hello"
    - cache_creation_input_tokens 0-5K
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
from pathlib import Path

DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_TIMEOUT = 120

# Published from scitex-agent-container's publish-agentic-test-image.yml
# workflow. Will eventually move to ghcr.io/ywatanabe1989/newb:latest.
DEFAULT_DOCKER_IMAGE = "ghcr.io/ywatanabe1989/scitex-agentic-test:latest"


class NewbieDockerRunner:
    """Run ``claude -p`` inside a long-lived newbie-docker container.

    A single container is reused across all calls for this process. Named
    ``newb-runner-<pid>`` and torn down via ``close()``; also registered
    with ``atexit`` so tests that crash still clean up.
    """

    def __init__(
        self,
        image: str | None = None,
        *,
        api_key_env: str = "ANTHROPIC_API_KEY",
        skills_mount: Path | None = None,
        system_prompt: str | None = None,
    ):
        self.image = (
            image or os.environ.get("NEWB_DOCKER_IMAGE") or DEFAULT_DOCKER_IMAGE
        )
        self.container_name = f"newb-runner-{os.getpid()}"
        self._started = False
        self.skills_mount = Path(skills_mount).resolve() if skills_mount else None
        self.system_prompt = system_prompt
        self._system_prompt_unsupported = False

        try:
            subprocess.run(
                ["docker", "version"],
                capture_output=True,
                check=True,
                timeout=10,
            )
        except FileNotFoundError as e:
            raise RuntimeError("NewbieDockerRunner requires `docker` on PATH.") from e
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"`docker version` failed — daemon not running? stderr="
                f"{e.stderr.decode(errors='replace')[:200]}"
            ) from e

        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(
                f"NewbieDockerRunner needs ${api_key_env} set "
                f"(used as ANTHROPIC_API_KEY inside the container)."
            )
        self._api_key = api_key
        atexit.register(self.close)

    def _start(self) -> None:
        if self._started:
            return
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
            check=False,
        )
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.container_name,
            "--network",
            "bridge",
            "-e",
            "CLAUDE_DISABLE_AUTO_UPDATE=1",
            "-e",
            f"ANTHROPIC_API_KEY={self._api_key}",
            "-e",
            "HOME=/home/agent",
        ]
        if self.skills_mount is not None:
            cmd += [
                "-v",
                f"{self.skills_mount}/.claude/skills:/home/agent/.claude/skills:ro",
            ]
        cmd += ["--entrypoint", "sleep", self.image, "infinity"]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            stderr = proc.stderr or ""
            if (
                "Unable to find image" in stderr
                or "manifest unknown" in stderr
                or "pull" in stderr.lower()
            ):
                pull = subprocess.run(
                    ["docker", "pull", self.image],
                    capture_output=True,
                    text=True,
                )
                if pull.returncode == 0:
                    proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"docker run failed for image {self.image!r}: {proc.stderr[:500]}"
                )
        self._started = True

    def run(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict:
        self._start()

        def _build_cmd(with_system_prompt: bool) -> list[str]:
            c = [
                "docker",
                "exec",
                "-u",
                "agent",
                "-e",
                "HOME=/home/agent",
                self.container_name,
                "claude",
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--verbose",
                "--model",
                model,
            ]
            if (
                with_system_prompt
                and self.system_prompt
                and not self._system_prompt_unsupported
            ):
                c += ["--append-system-prompt", self.system_prompt]
            return c

        def _one(with_sp: bool) -> subprocess.CompletedProcess:
            return subprocess.run(
                _build_cmd(with_sp),
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        proc = _one(with_sp=True)
        if (
            proc.returncode != 0
            and self.system_prompt
            and not self._system_prompt_unsupported
            and (
                "unknown option" in (proc.stderr + proc.stdout).lower()
                or "--system-prompt" in (proc.stderr + proc.stdout).lower()
                and "error" in (proc.stderr + proc.stdout).lower()
            )
        ):
            self._system_prompt_unsupported = True
            proc = _one(with_sp=False)

        if proc.returncode == 0 and not proc.stdout.strip():
            proc = _one(with_sp=not self._system_prompt_unsupported)

        if proc.returncode != 0:
            raise RuntimeError(
                f"docker exec claude -p failed (rc={proc.returncode}): "
                f"{proc.stderr[:500] or proc.stdout[:500]}"
            )
        if not proc.stdout.strip():
            raise RuntimeError("docker exec claude -p produced empty stdout twice")

        events: list[dict] = []
        final: dict = {}
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(obj)
            if isinstance(obj, dict) and obj.get("type") == "result":
                final = dict(obj)
        final["events"] = events
        return final

    def close(self) -> None:
        if not self._started:
            return
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True,
            check=False,
        )
        self._started = False


# EOF
