"""newb MCP module — lazy re-exports from _server.py.

The ``mcp`` global is what scitex-dev's audit-mcp-tools introspection
locates; we lazy-import to avoid pulling in fastmcp when the user
only wants the CLI/Python API.
"""

from __future__ import annotations


def __getattr__(name):
    if name in ("mcp", "run_server"):
        from newb._server import mcp, run_server

        globals()["mcp"] = mcp
        globals()["run_server"] = run_server
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["mcp", "run_server"]
