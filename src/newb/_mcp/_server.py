"""Top-level shim so scitex-dev's audit-mcp-tools can locate the MCP server.

Re-exports the FastMCP instance from ``newb._server``. Lazy import keeps
fastmcp out of the base install.
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
