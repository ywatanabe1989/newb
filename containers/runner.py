"""Inside-container runner — receives a prompt on argv, prints reply on stdout.

newb's DockerRunner / ApptainerRunner spawns this script with:

    <runtime> run --rm \\
        -v <staged>:/work/skills:ro \\
        -e ANTHROPIC_API_KEY \\
        ghcr.io/ywatanabe1989/newb-runner:VERSION \\
        "<prompt>"

The agent's filesystem horizon is /work/skills (the staged copy of the
package's docs). setting_sources=[] prevents auto-loading any
~/.claude/ context. allowed_tools=["Read"] confines the agent to file
reads. The container itself is the hard boundary — even if the agent
tried to escape, it has no host paths.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def _run(prompt: str, model: str) -> str:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    options = ClaudeAgentOptions(
        model=model,
        cwd="/work/skills",
        allowed_tools=["Read"],
        setting_sources=[],
        max_turns=8,
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


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: runner.py <prompt>", file=sys.stderr)
        return 2
    prompt = sys.argv[1]
    model = os.environ.get("NEWB_MODEL", "claude-haiku-4-5")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set in container env", file=sys.stderr)
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
