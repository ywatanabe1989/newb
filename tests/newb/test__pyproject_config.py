"""Tests for newb._pyproject_config — `[tool.newb]` defaults."""

from __future__ import annotations

import pytest

from newb._pyproject_config import load_pyproject_config, merged_defaults


def test_missing_pyproject_returns_empty(tmp_path):
    # Arrange
    # Act
    cfg = load_pyproject_config(tmp_path)
    # Assert
    assert cfg == {}


def test_pyproject_without_tool_newb_returns_empty(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
    )
    # Act
    cfg = load_pyproject_config(tmp_path)
    # Assert
    assert cfg == {}


def test_pyproject_tool_newb_parses_string_value(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text('[tool.newb]\ntemplate = "cli-tool"\n')
    # Act
    cfg = load_pyproject_config(tmp_path)
    # Assert
    assert cfg["template"] == "cli-tool"


def test_pyproject_tool_newb_parses_int_value(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text("[tool.newb]\nruns = 3\n")
    # Act
    cfg = load_pyproject_config(tmp_path)
    # Assert
    assert cfg["runs"] == 3


def test_pyproject_walks_up_to_find_config(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\nmodel = "claude-haiku-4-5"\n'
    )
    sub = tmp_path / "src" / "mypkg"
    sub.mkdir(parents=True)
    # Act
    cfg = load_pyproject_config(sub)
    # Assert
    assert cfg["model"] == "claude-haiku-4-5"


def test_merged_defaults_cli_runtime_overrides_pyproject(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\ntemplate = "python-package"\nruntime = "podman"\n'
    )
    # Act
    out = merged_defaults(tmp_path, runtime="docker", template=None)
    # Assert
    assert out["runtime"] == "docker"


def test_merged_defaults_preserves_pyproject_when_cli_absent(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\ntemplate = "python-package"\nruntime = "podman"\n'
    )
    # Act
    out = merged_defaults(tmp_path, runtime="docker", template=None)
    # Assert
    assert out["template"] == "python-package"


def test_merged_defaults_drops_unknown_keys(tmp_path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\ntemplate = "python-package"\nfuture_feature = "value"\n'
    )
    # Act
    out = merged_defaults(tmp_path)
    # Assert
    assert "future_feature" not in out
