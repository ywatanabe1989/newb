"""Tests for ``[tool.newb] mcp_servers`` validation + JSON encoding."""

from __future__ import annotations

import json

import pytest

from newb._mcp._inject import McpInjectError, encode_env, validate


def test_encode_env_none_returns_none():
    # Arrange
    # Act
    out = encode_env(None)
    # Assert
    assert out is None


def test_encode_env_empty_dict_returns_none():
    # Arrange
    # Act
    out = encode_env({})
    # Assert
    assert out is None


def test_encode_env_stdio_basename_round_trips_json():
    # Arrange
    servers = {"foo": {"type": "stdio", "command": "fooserver"}}
    # Act
    blob = encode_env(servers)
    # Assert
    assert json.loads(blob) == servers


def test_validate_stdio_container_abspath_ok():
    # Arrange
    servers = {"foo": {"type": "stdio", "command": "/usr/local/bin/foo"}}
    # Act
    out = validate(servers)
    # Assert
    assert out["foo"]["command"] == "/usr/local/bin/foo"


def test_validate_stdio_host_relative_path_rejected():
    # Arrange
    servers = {"foo": {"type": "stdio", "command": "./node_modules/.bin/foo"}}
    ctx = pytest.raises(McpInjectError, match="host-relative path")
    # Act
    # Assert
    with ctx:
        validate(servers)


def test_validate_stdio_host_absolute_outside_container_rejected():
    # Arrange
    servers = {"foo": {"type": "stdio", "command": "/home/user/.local/bin/foo"}}
    ctx = pytest.raises(McpInjectError, match="host-relative path")
    # Act
    # Assert
    with ctx:
        validate(servers)


def test_validate_http_url_passes_through():
    # Arrange
    servers = {"foo": {"type": "http", "url": "https://example.com/mcp"}}
    # Act
    out = validate(servers)
    # Assert
    assert out["foo"]["url"] == "https://example.com/mcp"


def test_validate_unknown_type_rejected():
    # Arrange
    ctx = pytest.raises(McpInjectError, match="must be one of")
    # Act
    # Assert
    with ctx:
        validate({"foo": {"type": "weird"}})


def test_validate_non_identifier_key_rejected():
    # Arrange
    ctx = pytest.raises(McpInjectError, match="must be an identifier")
    # Act
    # Assert
    with ctx:
        validate({"bad name!": {"type": "stdio", "command": "x"}})


def test_validate_non_table_rejected():
    # Arrange
    ctx = pytest.raises(McpInjectError, match="must be a table")
    # Act
    # Assert
    with ctx:
        validate(["nope"])  # type: ignore[arg-type]
