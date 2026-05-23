"""Tests for ``[tool.newb] mcp_servers`` validation + JSON encoding."""

from __future__ import annotations

import json

import pytest

from newb._mcp._inject import McpInjectError, encode_env, validate


def test_encode_env_none_returns_none():
    # Arrange
    inp = None
    # Act
    out = encode_env(inp)
    # Assert
    assert out is None


def test_encode_env_empty_dict_returns_none():
    # Arrange
    inp: dict = {}
    # Act
    out = encode_env(inp)
    # Assert
    assert out is None


def test_stdio_basename_command_encodes_as_json():
    # Arrange
    cfg = {"foo": {"type": "stdio", "command": "fooserver"}}
    # Act
    blob = encode_env(cfg)
    # Assert
    assert blob is not None and json.loads(blob) == cfg


def test_stdio_container_abspath_passes_through_validate():
    # Arrange
    cfg = {"foo": {"type": "stdio", "command": "/usr/local/bin/foo"}}
    # Act
    out = validate(cfg)
    # Assert
    assert out["foo"]["command"] == "/usr/local/bin/foo"


def test_stdio_host_relative_path_rejected():
    # Arrange
    cfg = {"foo": {"type": "stdio", "command": "./node_modules/.bin/foo"}}
    # Act
    ctx = pytest.raises(McpInjectError, match="host-relative path")
    # Assert
    with ctx:
        validate(cfg)


def test_stdio_host_absolute_outside_container_rejected():
    # Arrange
    cfg = {"foo": {"type": "stdio", "command": "/home/user/.local/bin/foo"}}
    # Act
    ctx = pytest.raises(McpInjectError, match="host-relative path")
    # Assert
    with ctx:
        validate(cfg)


def test_http_url_passes_through_validate():
    # Arrange
    cfg = {"foo": {"type": "http", "url": "https://example.com/mcp"}}
    # Act
    out = validate(cfg)
    # Assert
    assert out["foo"]["url"] == "https://example.com/mcp"


def test_unknown_type_rejected():
    # Arrange
    cfg = {"foo": {"type": "weird"}}
    # Act
    ctx = pytest.raises(McpInjectError, match="must be one of")
    # Assert
    with ctx:
        validate(cfg)


def test_bad_identifier_key_rejected():
    # Arrange
    cfg = {"bad name!": {"type": "stdio", "command": "x"}}
    # Act
    ctx = pytest.raises(McpInjectError, match="must be an identifier")
    # Assert
    with ctx:
        validate(cfg)


def test_non_table_top_level_rejected():
    # Arrange
    cfg = ["nope"]
    # Act
    ctx = pytest.raises(McpInjectError, match="must be a table")
    # Assert
    with ctx:
        validate(cfg)  # type: ignore[arg-type]


# EOF
