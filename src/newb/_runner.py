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


def _extract_oauth_token(cred_path: Path) -> str:
    """Extract the OAuth accessToken from a Claude Code credentials.json.

    Path layout::

        {"claudeAiOauth": {"accessToken": "sk-ant-oat01-...", ...}}

    The value can be a real dict or (in some saved formats) a Python-repr
    string; both are handled.
    """
    if not cred_path.is_file():
        raise RuntimeError(
            f"claude-code credential file not found: {cred_path}. "
            "Run `claude` once to authenticate, or pass a different path."
        )
    try:
        import ast as _ast
        import json as _json

        raw = _json.loads(cred_path.read_text(encoding="utf-8"))
        oauth = raw.get("claudeAiOauth")
        if isinstance(oauth, str):
            oauth = _ast.literal_eval(oauth)
        token = (oauth or {}).get("accessToken")
        if not token:
            raise KeyError("no accessToken in claudeAiOauth")
        return token
    except Exception as e:
        raise RuntimeError(
            f"could not extract OAuth token from {cred_path}: {e}"
        ) from e


class LocalRunner:
    """Run ``claude -p`` directly on the host with an isolated HOME.

    Unlike :class:`NewbieDockerRunner`, no docker. Subprocess uses an
    isolated ``HOME`` (default: a fresh tmp dir) so the agent only sees
    the staged ``.claude/skills/`` and never the user's real session.

    Auth modes:
      * ``api-key`` (default) — relies on ``ANTHROPIC_API_KEY`` env.
      * ``claude-code`` — copies host's ``~/.claude/.credentials*`` into
        the isolated HOME so a subscribed user can run without an API key.
    """

    def __init__(
        self,
        *,
        skills_mount: Path | None = None,
        api_key: str | None = None,
        claude_code_credential: str | None = None,
        config_dir: Path | None = None,
    ):
        import shutil as _sh
        import tempfile as _tmp

        if not _sh.which("claude"):
            raise RuntimeError("LocalRunner requires `claude` CLI on PATH.")

        self._owns_home = config_dir is None
        self.home = (
            Path(config_dir).expanduser().resolve()
            if config_dir
            else Path(_tmp.mkdtemp(prefix="newb-local-home-"))
        )
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
        # Path the agent will see when asked "read every .md under X".
        # (_verify.py reads this attribute; docker uses the default.)
        self.skills_path = str(self.home / ".claude" / "skills")

        if skills_mount is not None:
            src = Path(skills_mount) / ".claude" / "skills"
            if src.is_dir():
                for child in src.iterdir():
                    dst = self.home / ".claude" / "skills" / child.name
                    if dst.exists():
                        _sh.rmtree(dst, ignore_errors=True)
                    _sh.copytree(child, dst)

        self.env = os.environ.copy()
        self.env["HOME"] = str(self.home)
        self.env["CLAUDE_DISABLE_AUTO_UPDATE"] = "1"

        # Auth resolution. Two independent options; each cascades
        # CLI-flag → env-var → unset (mirrors scitex-config PriorityConfig).
        # When both resolve, claude-code-credential wins (subscription
        # quota → $0 marginal vs per-call $$$ on api-key).
        cc_path = claude_code_credential or os.environ.get(
            "NEWB_CLAUDE_CODE_CREDENTIAL"
        )
        api_key_value = api_key or os.environ.get("NEWB_ANTHROPIC_API_KEY")
        token = None
        if cc_path:
            token = _extract_oauth_token(Path(cc_path).expanduser())
        elif api_key_value:
            token = api_key_value
        if not token:
            raise RuntimeError(
                "LocalRunner: no auth resolved. Provide either:\n"
                "  --claude-code-credential PATH (or $NEWB_CLAUDE_CODE_CREDENTIAL) "
                "→ subscription quota, $0 marginal\n"
                "  --api-key TOKEN (or $NEWB_ANTHROPIC_API_KEY) "
                "→ per-call API spend"
            )
        self.env["ANTHROPIC_API_KEY"] = token
        atexit.register(self.close)

    def run(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict:
        # `--bare` mode is the isolation primitive: skips hooks, LSP,
        # plugin sync, attribution, auto-memory, background prefetches,
        # keychain reads, and CLAUDE.md auto-discovery. Auth must come
        # from ANTHROPIC_API_KEY (no OAuth, no host ~/.claude leak).
        # `--add-dir <skills_path>` explicitly grants read access to the
        # staged skills, sidestepping claude's CWD-based file access guard.
        cmd = [
            "claude",
            "--bare",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--model",
            model,
            "--add-dir",
            self.skills_path,
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self.env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"local claude -p failed (rc={proc.returncode}): "
                f"{proc.stderr[:500] or proc.stdout[:500]}"
            )
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
        if self._owns_home and self.home.exists():
            import shutil as _sh

            _sh.rmtree(self.home, ignore_errors=True)


# EOF
