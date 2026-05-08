"""Tests for ``[tool.newb] mcp_servers`` validation + JSON encoding."""

from __future__ import annotations

import json

import pytest

from newb._mcp._inject import McpInjectError, encode_env, validate


def test_empty_returns_none():
    assert encode_env(None) is None
    assert encode_env({}) is None


def test_stdio_basename_ok():
    blob = encode_env({"foo": {"type": "stdio", "command": "fooserver"}})
    assert blob is not None
    assert json.loads(blob) == {"foo": {"type": "stdio", "command": "fooserver"}}


def test_stdio_container_abspath_ok():
    out = validate({"foo": {"type": "stdio", "command": "/usr/local/bin/foo"}})
    assert out["foo"]["command"] == "/usr/local/bin/foo"


def test_stdio_host_relative_path_rejected():
    with pytest.raises(McpInjectError, match="host-relative path"):
        validate({"foo": {"type": "stdio", "command": "./node_modules/.bin/foo"}})


def test_stdio_host_absolute_outside_container_rejected():
    with pytest.raises(McpInjectError, match="host-relative path"):
        validate({"foo": {"type": "stdio", "command": "/home/user/.local/bin/foo"}})


def test_http_passes_through():
    out = validate({"foo": {"type": "http", "url": "https://example.com/mcp"}})
    assert out["foo"]["url"] == "https://example.com/mcp"


def test_unknown_type_rejected():
    with pytest.raises(McpInjectError, match="must be one of"):
        validate({"foo": {"type": "weird"}})


def test_bad_key_rejected():
    with pytest.raises(McpInjectError, match="must be an identifier"):
        validate({"bad name!": {"type": "stdio", "command": "x"}})


def test_non_table_rejected():
    with pytest.raises(McpInjectError, match="must be a table"):
        validate(["nope"])  # type: ignore[arg-type]


# EOF
