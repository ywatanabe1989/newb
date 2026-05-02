"""Validate + encode ``[tool.newb] mcp_servers`` for container forwarding.

A user-declared ``mcp_servers`` table flows host → container via a
single JSON env var (``NEWB_MCP_SERVERS_JSON``). The container runner
decodes it and feeds it straight to ``ClaudeAgentOptions(mcp_servers=...)``.

Validation is intentionally narrow:

- Keys must be identifier-shaped (the SDK uses them as labels).
- Each value must be a dict with a ``type`` field (``stdio`` | ``http``
  | ``sse``) — the same shapes ``ClaudeAgentOptions`` accepts.
- For ``stdio`` servers, ``command`` must be either a basename
  (resolved on the container's PATH) or an absolute path that already
  looks container-side (``/usr/...``, ``/work/...``). Host-relative
  paths are rejected because they won't resolve inside the container.

We deliberately do *not* validate ``http``/``sse`` URLs — the agent
is already inside the container's network namespace; the user owns
the trust decision when they put a URL in their own pyproject.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_CONTAINER_ABSPATH_PREFIXES = ("/usr/", "/bin/", "/sbin/", "/work/", "/opt/", "/etc/")


class McpInjectError(ValueError):
    """Raised when ``[tool.newb] mcp_servers`` is malformed or unsafe."""


def validate(servers: Mapping[str, Any]) -> dict[str, dict]:
    """Return a normalized servers dict, or raise ``McpInjectError``."""
    if not isinstance(servers, Mapping):
        raise McpInjectError(
            f"[tool.newb] mcp_servers must be a table, not {type(servers).__name__}."
        )
    out: dict[str, dict] = {}
    for name, cfg in servers.items():
        if not isinstance(name, str) or not _IDENT.match(name):
            raise McpInjectError(
                f"mcp_servers key {name!r} must be an identifier "
                "(letters, digits, underscore, hyphen; starting with a letter "
                "or underscore)."
            )
        if not isinstance(cfg, Mapping):
            raise McpInjectError(
                f"mcp_servers.{name} must be a table, not {type(cfg).__name__}."
            )
        kind = cfg.get("type")
        if kind not in {"stdio", "http", "sse"}:
            raise McpInjectError(
                f"mcp_servers.{name}.type must be one of 'stdio' | 'http' | 'sse'."
            )
        if kind == "stdio":
            cmd = cfg.get("command")
            if not isinstance(cmd, str) or not cmd:
                raise McpInjectError(
                    f"mcp_servers.{name}.command (string) is required for "
                    "stdio servers."
                )
            if "/" in cmd and not cmd.startswith(_CONTAINER_ABSPATH_PREFIXES):
                raise McpInjectError(
                    f"mcp_servers.{name}.command={cmd!r} looks like a "
                    "host-relative path. Use a basename (resolved on the "
                    "container's PATH) or an absolute path that exists "
                    "inside the container "
                    f"(prefixes: {', '.join(_CONTAINER_ABSPATH_PREFIXES)})."
                )
        out[name] = dict(cfg)
    return out


def encode_env(servers: Mapping[str, Any] | None) -> str | None:
    """Validate + JSON-encode for ``NEWB_MCP_SERVERS_JSON``. Returns
    ``None`` when ``servers`` is empty/None — caller should skip the
    env var in that case so the container sees the SDK default."""
    if not servers:
        return None
    return json.dumps(validate(servers), separators=(",", ":"))


# EOF
