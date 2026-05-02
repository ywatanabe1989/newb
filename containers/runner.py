"""Inside-container runner — receives a prompt on argv, prints reply on stdout.

newb's DockerRunner / ApptainerRunner spawns this script with:

    <runtime> run --rm \\
        -v <staged-project>:/work/project \\
        -e NEWB_ANTHROPIC_API_KEY \\
        -e NEWB_MODEL \\
        -e NEWB_SKILLS_PATH \\
        ghcr.io/ywatanabe1989/newb-runner:VERSION \\
        "<prompt>"

Auth: ONE env var, ``NEWB_ANTHROPIC_API_KEY``. This script promotes it
to ``ANTHROPIC_API_KEY`` for the bundled CLI. The Anthropic backend
accepts both real API keys (``sk-ant-api*``) and Claude Code OAuth
access tokens (``sk-ant-oat*``) in the same Authorization header — no
host-side dispatch or credentials-file translation needed.

Container is the boundary, not the SDK options. The agent's filesystem
horizon is /work/project (the staged copy of the project). Inside the
container the agent gets FULL agentic permissions — Read + Write +
Edit + Bash + Glob + Grep — so it can actually install + try the
package. ``setting_sources=[]`` still prevents auto-loading any
~/.claude/ context (the host's CLAUDE.md never reaches the agent).
"""

from __future__ import annotations

import asyncio
import os
import sys


def _provision_auth() -> bool:
    """Promote NEWB_ANTHROPIC_API_KEY to ANTHROPIC_API_KEY for the
    bundled CLI. The Anthropic backend accepts both real API keys
    (sk-ant-api*) and Claude Code OAuth access tokens (sk-ant-oat*)
    in the same Authorization header — no prefix detection needed.

    Returns True on success, False if no token was supplied.
    """
    token = os.environ.get("NEWB_ANTHROPIC_API_KEY", "").strip()
    if not token:
        return False
    os.environ["ANTHROPIC_API_KEY"] = token
    return True


async def _run(prompt: str, model: str) -> str:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    # Scope policy:
    #   - "all"  (default) — let permission_mode="acceptEdits" carry the
    #     policy. No allowed_tools restriction; agent can install + run
    #     + test the package (newb's core value).
    #   - "docs" — read-only audit mode. Agent gets just Read/Glob/Grep
    #     so it can scan the project but not modify it or shell out.
    scope = os.environ.get("NEWB_SCOPE", "all").lower()
    # Container is the boundary, not the SDK options. Inside, we want
    # full agentic execution so post_install_check can actually run
    # `pip install -e .` etc. — `acceptEdits` only auto-approves edits
    # and would prompt on Bash, deadlocking the non-interactive runner.
    # `bypassPermissions` is the SDK equivalent of
    # `--dangerously-skip-permissions`. Safe here because the container
    # is single-shot, network is bridge-only, and the staged project is
    # the agent's whole filesystem horizon.
    permission_mode = "bypassPermissions" if scope == "all" else "acceptEdits"
    sdk_kwargs = {
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
        import json

        try:
            sdk_kwargs["mcp_servers"] = json.loads(mcp_blob)
        except json.JSONDecodeError as e:
            print(
                f"NEWB_MCP_SERVERS_JSON decode failed: {e}",
                file=sys.stderr,
            )
    options = ClaudeAgentOptions(**sdk_kwargs)

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


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: runner.py <prompt>", file=sys.stderr)
        return 2
    prompt = sys.argv[1]
    model = os.environ.get("NEWB_MODEL", "claude-haiku-4-5")
    if not _provision_auth():
        print(
            "NEWB_ANTHROPIC_API_KEY not set in container env — host "
            "runner must forward it (the value is opaque: API key "
            "sk-ant-api* or Claude Code OAuth token sk-ant-oat*).",
            file=sys.stderr,
        )
        return 3
    try:
        text = asyncio.run(_run(prompt, model))
    except Exception as e:
        print(f"runner error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
