"""SDK-backed runner: drives Claude via Anthropic's official ``claude-agent-sdk``.

Replaces the sac+A2A pipeline (newb 0.6) with a direct SDK call. Reasons:

* SDK is purpose-built for programmatic agent invocation — short, fast,
  no docker / multiplexer / wire format.
* Survives ``claude --print`` deprecation (SDK uses structured streaming).
* Works with both API key and OAuth (Max plan) auth — the bundled CLI
  honors the same ``ANTHROPIC_API_KEY`` env var and falls back to
  ``~/.claude/.credentials.json`` if neither is set.

Auth — newb owns its own env namespace (NEWB_ prefix only) so it never
silently picks up an upstream ``ANTHROPIC_API_KEY`` the user set for
something else:

* Set ``NEWB_ANTHROPIC_API_KEY`` to opt newb into API key auth (canonical
  for production / CI / redistributed use). Forwarded to the SDK as
  ``ANTHROPIC_API_KEY`` only for the duration of the call, then restored.
* If ``NEWB_ANTHROPIC_API_KEY`` is unset, newb actively *masks* any stray
  ``ANTHROPIC_API_KEY`` in the environment for the SDK call so the
  bundled CLI falls through to ``~/.claude/`` OAuth login (personal-use
  gray zone per Anthropic's commercial ToS) or fails cleanly.

Isolation:

* ``setting_sources=[]`` — don't auto-load the host's ``CLAUDE.md`` /
  ``.claude/`` settings / skills. The agent sees only what we pass.
* ``allowed_tools=["Read"]`` — only file reads. No Bash, no Write, no
  WebFetch. The agent can read .md files in the staged dir and that's
  the entire surface available for hallucination.
* ``cwd=<staged_dir>`` — the agent's working dir is the skills source.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path


class SdkRunner:
    """One-shot-per-prompt runner using ``claude_agent_sdk.query``.

    Each ``run(prompt)`` opens a fresh independent query — no shared
    conversation state, so questions don't influence each other. The
    SDK handles all transport, message structuring, and lifecycle.
    """

    def __init__(
        self,
        *,
        skills_mount: Path,
        model: str = "claude-haiku-4-5",
    ):
        try:
            from claude_agent_sdk import (  # noqa: F401
                ClaudeAgentOptions,
                query,
            )
        except ImportError as e:
            raise RuntimeError(
                "SdkRunner requires `claude-agent-sdk` "
                "(`pip install claude-agent-sdk`)."
            ) from e
        self.skills_mount = Path(skills_mount).resolve()
        self.model = model
        # Stage the skills under a clean tmp cwd so the agent's Read tool
        # is bounded to the package's content (no leakage from the
        # caller's filesystem).
        self._tmp_cwd = Path(tempfile.mkdtemp(prefix="newb-sdk-cwd-"))
        target = self._tmp_cwd / self.skills_mount.name
        shutil.copytree(self.skills_mount, target)
        # The path the prompts will reference.
        self.skills_path = str(self._tmp_cwd)

    def run(self, prompt: str, *, model: str | None = None, timeout: int = 120) -> dict:
        """POST a single prompt to the SDK; return ``{"result": text}``.

        Returned shape is compatible with newb's ``_extract_text`` helper.
        """
        return asyncio.run(self._run_async(prompt, model or self.model, timeout))

    async def _run_async(self, prompt: str, model: str, timeout: int) -> dict:
        import os

        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            query,
        )

        # NEWB_ prefix only — never silently inherit ANTHROPIC_API_KEY from
        # the user's shell environment. Forward the explicit
        # NEWB_ANTHROPIC_API_KEY to the SDK by temporarily setting the
        # canonical env var; if NEWB_ANTHROPIC_API_KEY is unset, mask any
        # stray ANTHROPIC_API_KEY so the SDK's bundled CLI falls through to
        # the personal-machine ~/.claude/ OAuth login (or fails cleanly).
        prior_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        newb_key = os.environ.get("NEWB_ANTHROPIC_API_KEY")
        if newb_key:
            os.environ["ANTHROPIC_API_KEY"] = newb_key
        elif prior_anthropic_key is not None:
            os.environ.pop("ANTHROPIC_API_KEY", None)

        options = ClaudeAgentOptions(
            model=model,
            cwd=self.skills_path,
            allowed_tools=["Read"],
            setting_sources=[],  # do NOT inherit host context
            max_turns=8,  # bounded — agent should answer in 1-3 reads
        )

        text_chunks: list[str] = []
        result_text: str | None = None

        async def _consume() -> None:
            nonlocal result_text
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_chunks.append(block.text)
                elif isinstance(message, ResultMessage):
                    # ResultMessage is the final summary; prefer its text.
                    if hasattr(message, "result") and message.result:
                        result_text = str(message.result)

        try:
            await asyncio.wait_for(_consume(), timeout=timeout)
        except asyncio.TimeoutError:
            return {
                "result": f"(SDK timeout after {timeout}s; partial: {''.join(text_chunks)[:200]})"
            }
        finally:
            # Restore the user's original env exactly.
            if prior_anthropic_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = prior_anthropic_key

        text = result_text or "\n".join(text_chunks).strip() or "(empty response)"
        return {"result": text}

    def close(self) -> None:
        if self._tmp_cwd.exists():
            shutil.rmtree(self._tmp_cwd, ignore_errors=True)
