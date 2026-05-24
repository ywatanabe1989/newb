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

from ._hardening import HardeningOptions, apptainer_hardening_argv, hardening_argv
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
# A batch of N prompts shares ONE container, so the wall-clock budget
# must scale with N. Per-prompt budget is the old 240s; the wrapper
# multiplies by len(prompts) and pads for container startup.
PER_PROMPT_TIMEOUT_S = 240
CONTAINER_STARTUP_PAD_S = 60


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
        mcp_servers: dict | None = None,
        pip_cache_dir: str | None = None,
        which=None,
    ):
        # `which` is injectable so tests can run without the real
        # docker/apptainer binaries on PATH. Production callers leave
        # it as ``None`` and we use ``shutil.which`` — no patching.
        if which is None:
            which = shutil.which
        if not which(self.runtime_bin):
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
        # OAuth flat-rate path: bind-mount a credentials.json into the
        # container so the SDK uses the file-based auth flow instead
        # of the bare-env path. Anthropic rejects ``sk-ant-oat01-…``
        # OAuth tokens passed as ``ANTHROPIC_API_KEY`` env vars (no
        # refresh-token / expiresAt context); the file gives them the
        # full credentials shape they expect. The env var still flows
        # for ``sk-ant-api*`` real API keys, which work fine bare.
        #
        # Resolution order:
        #   1. ``$NEWB_CLAUDE_CODE_CREDENTIALS_JSON`` — full file contents as the
        #      env-var value. Materialise to a 0600 tempfile and
        #      bind-mount that. Intended for CI: the workflow puts a
        #      single secret in this env var, no shell provisioning
        #      step needed. We own the file so the chmod is correct.
        #   2. ``~/.claude/.credentials.json`` exists on the host —
        #      bind-mount the original file (local-dev path).
        #   3. Neither — env-var-only auth (works for sk-ant-api* keys).
        self._credentials_tempfile: Path | None = None
        env_creds = os.environ.get("NEWB_CLAUDE_CODE_CREDENTIALS_JSON", "").strip()
        if env_creds:
            tmp = tempfile.NamedTemporaryFile(
                "w", prefix="newb-creds-", suffix=".json", delete=False
            )
            tmp.write(env_creds)
            tmp.close()
            os.chmod(tmp.name, 0o644)  # readable by container's newb uid
            self._credentials_tempfile = Path(tmp.name)
            self._host_credentials_json: Path | None = self._credentials_tempfile
        else:
            host_creds = Path("~/.claude/.credentials.json").expanduser()
            self._host_credentials_json = host_creds if host_creds.is_file() else None
        # Validated host-side; container-side runner trusts the encoded
        # JSON. Empty / None → no NEWB_MCP_SERVERS_JSON env var, container
        # gets the SDK default (no MCP servers).
        from ._mcp._inject import encode_env as _mcp_encode_env

        self._mcp_servers_env = _mcp_encode_env(mcp_servers)
        # Optional host-side pip cache; mounted into the container as
        # the agent's `~/.cache/pip` so repeated `newb` runs in local
        # dev don't re-download every wheel. Created on demand. Leave
        # unset (the default) for CI — cold install is the honest
        # newbie test.
        cache_env = os.environ.get("NEWB_PIP_CACHE_DIR", "").strip()
        chosen = pip_cache_dir if pip_cache_dir is not None else cache_env
        if chosen:
            cache_path = Path(chosen).expanduser()
            cache_path.mkdir(parents=True, exist_ok=True)
            self._pip_cache_host = str(cache_path)
        else:
            self._pip_cache_host = None
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

    def _build_argv(self) -> list[str]:
        """Return the runtime argv up to (and including) the image; the
        in-container runner reads its prompt batch from stdin."""
        raise NotImplementedError

    def _with_env(self, argv: list[str], name: str, value: str) -> list[str]:
        """Insert an env-var pair before the image tag. Docker/podman use
        ``-e NAME=VALUE``; apptainer uses ``--env NAME=VALUE``. Last argv
        element is always the image (or ``docker://image``) — splice in
        front of it."""
        flag = "--env" if self.runtime_bin == "apptainer" else "-e"
        return argv[:-1] + [flag, f"{name}={value}", argv[-1]]

    def run_batch(
        self,
        prompts: list[str],
        *,
        model: str | None = None,
        timeout: int | None = None,
        verbosity: int = 0,
    ) -> list[dict]:
        """Run all ``prompts`` in a single container invocation.

        One docker/apptainer/podman startup, one project stage, one SDK
        options object — but per-prompt independent ``query()`` calls,
        so on-disk state (``pip install -e .``) carries between prompts
        while conversation context does not. Returns a list of
        ``{"result": str}`` dicts, in input order.

        ``verbosity`` (0..3):
          * 0: stderr captured silently (default).
          * 1: same as 0 host-side; container also receives
            ``NEWB_VERBOSE=1`` so it emits per-prompt timing on stderr,
            replayed at the end if the run fails.
          * 2: stderr inherited — the container's per-prompt timing
            and SDK chatter stream live to the host.
          * 3: -vv plus the host logs the raw container argv.
        """
        if not prompts:
            return []
        import json as _json
        import sys as _sys

        if timeout is None:
            timeout = PER_PROMPT_TIMEOUT_S * len(prompts) + CONTAINER_STARTUP_PAD_S
        argv = self._build_argv()
        # Inject per-prompt timing inside the container when -v or higher.
        if verbosity >= 1:
            argv = self._with_env(argv, "NEWB_VERBOSE", str(verbosity))
        if verbosity >= 3:
            print(
                f"newb: container argv: {' '.join(argv)}",
                file=_sys.stderr,
                flush=True,
            )
        payload = _json.dumps({"prompts": list(prompts)})
        # -vv+ inherits stderr so the container's progress lines land
        # on the host stderr in real time (otherwise they're captured
        # and only shown on failure).
        stderr_dest = None if verbosity >= 2 else subprocess.PIPE
        try:
            proc = subprocess.run(
                argv,
                input=payload,
                stdout=subprocess.PIPE,
                stderr=stderr_dest,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            stub = {"result": f"(container timeout after {timeout}s)"}
            return [stub for _ in prompts]
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:500]
            raise RuntimeError(
                f"{self.runtime_bin} runner failed (rc={proc.returncode}): {err}"
            )
        try:
            envelope = _json.loads(proc.stdout)
            results = envelope["results"]
            assert isinstance(results, list) and len(results) == len(prompts)
        except (_json.JSONDecodeError, KeyError, AssertionError) as e:
            raise RuntimeError(
                f"{self.runtime_bin} runner returned bad envelope "
                f"({type(e).__name__}: {e}); stdout head: "
                f"{proc.stdout[:200]!r}"
            ) from e
        return [{"result": (r or "").strip() or "(empty response)"} for r in results]

    def run(
        self, prompt: str, *, model: str | None = None, timeout: int = DEFAULT_TIMEOUT_S
    ) -> dict:
        """Single-prompt convenience wrapper around ``run_batch``."""
        return self.run_batch([prompt], model=model, timeout=timeout)[0]

    def close(self) -> None:
        if self._stage_dir.exists():
            shutil.rmtree(self._stage_dir, ignore_errors=True)
        # Tempfile owned by us (materialised from NEWB_CLAUDE_CODE_CREDENTIALS_JSON)
        # — host-side host file lifetimes are not ours to delete.
        if (
            self._credentials_tempfile is not None
            and self._credentials_tempfile.exists()
        ):
            try:
                self._credentials_tempfile.unlink()
            except OSError:
                pass


class DockerRunner(_BaseContainerRunner):
    """Runs the SDK call inside a docker container."""

    runtime_bin = "docker"

    def _build_argv(self) -> list[str]:
        project_host = str(self._stage_target)
        # `-i` keeps stdin open so the in-container runner can read the
        # batch JSON envelope. Forward NEWB_ANTHROPIC_API_KEY into the
        # container; the in-container runner.py promotes it to
        # ANTHROPIC_API_KEY for the bundled CLI. The Anthropic backend
        # accepts both real API keys (sk-ant-api*) and Claude Code OAuth
        # access tokens (sk-ant-oat*) on the same code path.
        argv = ["docker", "run", "--rm", "-i"]
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
        ]
        if self._mcp_servers_env:
            argv += ["-e", f"NEWB_MCP_SERVERS_JSON={self._mcp_servers_env}"]
        if self._pip_cache_host:
            argv += ["-v", f"{self._pip_cache_host}:/home/newb/.cache/pip"]
        if self._host_credentials_json is not None:
            # Mount read-only at the agent user's $HOME path so the
            # bundled CLI's credentials_file lookup picks it up.
            argv += [
                "-v",
                f"{self._host_credentials_json}:/home/newb/.claude/.credentials.json:ro",
            ]
        argv += [self.image]
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

    def _build_argv(self) -> list[str]:
        argv = super()._build_argv()
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

    def _build_argv(self) -> list[str]:
        project_host = str(self._stage_target)
        argv = ["apptainer", "run", "--no-home", "--containall"]
        argv += apptainer_hardening_argv(self.hardening)
        argv += [
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
        ]
        if self._mcp_servers_env:
            argv += [
                "--env",
                f"NEWB_MCP_SERVERS_JSON={self._mcp_servers_env}",
            ]
        if self._pip_cache_host:
            argv += ["--bind", f"{self._pip_cache_host}:/home/newb/.cache/pip"]
        if self._host_credentials_json is not None:
            argv += [
                "--bind",
                f"{self._host_credentials_json}:/home/newb/.claude/.credentials.json:ro",
            ]
        argv += [f"docker://{self.image}"]
        return argv
