"""Inside-container runner — receives prompt(s), prints reply/replies on stdout.

Two invocation modes:

* **Single-prompt (legacy)**: ``runner.py "<prompt>"`` — emits plain
  text on stdout. Used by hosts that want one-shot behavior.
* **Batch (preferred)**: a JSON envelope on stdin of the shape
  ``{"prompts": ["...", "..."]}``. Emits a JSON envelope on stdout of
  the shape ``{"results": ["...", "..."]}``, in input order.
  Used by ``newb`` so all template questions share **one** container
  startup + project stage. ``post_install_check`` writes
  ``pip install -e .``-state visible to subsequent prompts because the
  container's filesystem persists across the per-prompt ``query()``
  calls.

newb's DockerRunner / ApptainerRunner spawns this script with::

    <runtime> run --rm -i \\
        -v <staged-project>:/work/project \\
        -e NEWB_ANTHROPIC_API_KEY \\
        -e NEWB_MODEL \\
        -e NEWB_SKILLS_PATH \\
        ghcr.io/ywatanabe1989/newb-runner:VERSION    # batch mode: stdin JSON
        # or trailing "<prompt>" for single-prompt mode

Auth: ONE env var, ``NEWB_ANTHROPIC_API_KEY``. This script promotes it
to ``ANTHROPIC_API_KEY`` for the bundled CLI. The Anthropic backend
accepts both real API keys (``sk-ant-api*``) and Claude Code OAuth
access tokens (``sk-ant-oat*``) in the same Authorization header.

Container is the boundary, not the SDK options. The agent's filesystem
horizon is /work/project (the staged copy of the project). Inside the
container the agent gets FULL agentic permissions — Read + Write +
Edit + Bash + Glob + Grep — so it can actually install + try the
package. ``setting_sources=[]`` still prevents auto-loading any
~/.claude/ context (the host's CLAUDE.md never reaches the agent).
"""

from __future__ import annotations

import asyncio
import json
import os
import select
import sys


def _provision_auth() -> bool:
    """Promote NEWB_ANTHROPIC_API_KEY → ANTHROPIC_API_KEY. Returns
    False if no token was supplied."""
    token = os.environ.get("NEWB_ANTHROPIC_API_KEY", "").strip()
    if not token:
        return False
    os.environ["ANTHROPIC_API_KEY"] = token
    return True


def _build_sdk_kwargs(model: str) -> dict:
    """Resolve the SDK options once; reused across every prompt in the
    batch so all queries share cwd, permission policy, and MCP servers."""
    scope = os.environ.get("NEWB_SCOPE", "all").lower()
    # `bypassPermissions` is the SDK equivalent of
    # `--dangerously-skip-permissions`. Safe here because the container
    # is the boundary; `--scope docs` keeps `acceptEdits` + an
    # allowed_tools allowlist that excludes Bash/Write/Edit.
    permission_mode = "bypassPermissions" if scope == "all" else "acceptEdits"
    sdk_kwargs: dict = {
        "model": model,
        "cwd": os.environ.get("NEWB_CWD", "/work/project"),
        "permission_mode": permission_mode,
        "setting_sources": [],
        "max_turns": 15,
    }
    if scope == "docs":
        sdk_kwargs["allowed_tools"] = ["Read", "Glob", "Grep"]
    mcp_blob = os.environ.get("NEWB_MCP_SERVERS_JSON", "").strip()
    if mcp_blob:
        try:
            sdk_kwargs["mcp_servers"] = json.loads(mcp_blob)
        except json.JSONDecodeError as e:
            print(f"NEWB_MCP_SERVERS_JSON decode failed: {e}", file=sys.stderr)
    return sdk_kwargs


async def _run_one(prompt: str, options) -> str:
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        TextBlock,
        query,
    )

    chunks: list[str] = []
    final_text: str | None = None
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, TextBlock):
                    chunks.append(b.text)
        elif isinstance(msg, ResultMessage):
            if hasattr(msg, "result") and msg.result:
                final_text = str(msg.result)
    return final_text or "\n".join(chunks).strip() or "(empty response)"


async def _run_all(prompts: list[str], model: str) -> list[str]:
    """Build options once, run every prompt sequentially as an
    independent ``query()`` so they share cwd / installed-state on
    disk but do not pollute each other's conversation context."""
    from claude_agent_sdk import ClaudeAgentOptions

    options = ClaudeAgentOptions(**_build_sdk_kwargs(model))
    results: list[str] = []
    for prompt in prompts:
        results.append(await _run_one(prompt, options))
    return results


def _read_stdin_if_piped() -> str:
    """Return stdin contents iff something is actually piped (avoid
    blocking when no batch payload was sent)."""
    if sys.stdin.isatty():
        return ""
    # On some runtimes (apptainer with --no-home) stdin may be a TTY-ish
    # FIFO; select with a short timeout avoids hanging forever.
    try:
        readable, _, _ = select.select([sys.stdin], [], [], 0.5)
    except Exception:
        readable = [sys.stdin]
    if not readable:
        return ""
    return sys.stdin.read()


def main() -> int:
    model = os.environ.get("NEWB_MODEL", "claude-haiku-4-5")
    if not _provision_auth():
        print(
            "NEWB_ANTHROPIC_API_KEY not set in container env — host "
            "runner must forward it (the value is opaque: API key "
            "sk-ant-api* or Claude Code OAuth token sk-ant-oat*).",
            file=sys.stderr,
        )
        return 3

    raw = _read_stdin_if_piped().strip()
    if raw:
        try:
            envelope = json.loads(raw)
            prompts = envelope["prompts"]
            assert isinstance(prompts, list) and all(
                isinstance(p, str) for p in prompts
            )
        except (json.JSONDecodeError, KeyError, AssertionError) as e:
            print(
                f"runner error: bad batch envelope ({type(e).__name__}: {e}); "
                'expected {"prompts": ["...", ...]}',
                file=sys.stderr,
            )
            return 4
        try:
            results = asyncio.run(_run_all(prompts, model))
        except Exception as e:
            print(f"runner error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        json.dump({"results": results}, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return 0

    if len(sys.argv) < 2:
        print(
            'usage: runner.py "<prompt>"   OR   pipe {"prompts":[...]} on stdin',
            file=sys.stderr,
        )
        return 2
    try:
        results = asyncio.run(_run_all([sys.argv[1]], model))
    except Exception as e:
        print(f"runner error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(results[0])
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
