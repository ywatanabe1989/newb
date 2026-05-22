"""Tests for newb._pyproject_config — `[tool.newb]` defaults."""

from __future__ import annotations

import pytest


def test_missing_pyproject_returns_empty(tmp_path):
    # Arrange
    from newb._pyproject_config import load_pyproject_config

    # Act
    out = load_pyproject_config(tmp_path)
    # Assert
    assert out == {}


def test_pyproject_without_tool_newb_returns_empty(tmp_path):
    # Arrange
    from newb._pyproject_config import load_pyproject_config

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
    )
    # Act
    out = load_pyproject_config(tmp_path)
    # Assert
    assert out == {}


# ---------------------------------------------------------------------------
# tool.newb parsing — fixture loads the file once, split asserts per key.
# ---------------------------------------------------------------------------


@pytest.fixture
def _tool_newb_cfg(tmp_path):
    """One pyproject.toml with a populated [tool.newb] block; share across
    the per-key assertions below so each test stays one-Act."""
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import load_pyproject_config

    (tmp_path / "pyproject.toml").write_text(
        "[tool.newb]\n"
        'template = "cli-tool"\n'
        'runtime = "podman"\n'
        'scope = "docs"\n'
        "runs = 3\n"
    )
    return load_pyproject_config(tmp_path)


def test_pyproject_tool_newb_parses_template(_tool_newb_cfg):
    # Arrange
    cfg = _tool_newb_cfg
    # Act
    value = cfg.get("template")
    # Assert
    assert value == "cli-tool"


def test_pyproject_tool_newb_parses_runtime(_tool_newb_cfg):
    # Arrange
    cfg = _tool_newb_cfg
    # Act
    value = cfg.get("runtime")
    # Assert
    assert value == "podman"


def test_pyproject_tool_newb_parses_scope(_tool_newb_cfg):
    # Arrange
    cfg = _tool_newb_cfg
    # Act
    value = cfg.get("scope")
    # Assert
    assert value == "docs"


def test_pyproject_tool_newb_parses_runs_as_int(_tool_newb_cfg):
    # Arrange
    cfg = _tool_newb_cfg
    # Act
    value = cfg.get("runs")
    # Assert
    assert value == 3


def test_pyproject_walks_up_to_find_config(tmp_path):
    """If `start` is a sub-dir, walk up to find pyproject.toml."""
    # Arrange
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import load_pyproject_config

    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\nmodel = "claude-haiku-4-5"\n'
    )
    sub = tmp_path / "src" / "mypkg"
    sub.mkdir(parents=True)
    # Act
    cfg = load_pyproject_config(sub)
    # Assert
    assert cfg["model"] == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# merged_defaults — CLI > pyproject precedence.
# ---------------------------------------------------------------------------


@pytest.fixture
def _merged_cli_over_pyproject(tmp_path):
    """``[tool.newb]`` sets runtime=podman; CLI passes runtime=docker."""
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import merged_defaults

    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\ntemplate = "python-package"\nruntime = "podman"\n'
    )
    return merged_defaults(tmp_path, runtime="docker", template=None)


def test_merged_defaults_cli_wins_for_explicit_overrides(_merged_cli_over_pyproject):
    # Arrange
    out = _merged_cli_over_pyproject
    # Act
    runtime = out["runtime"]
    # Assert
    assert runtime == "docker"  # CLI wins


def test_merged_defaults_pyproject_preserved_when_cli_absent(
    _merged_cli_over_pyproject,
):
    # Arrange
    out = _merged_cli_over_pyproject
    # Act
    template = out["template"]
    # Assert
    assert template == "python-package"  # pyproject preserved


def test_merged_defaults_unknown_keys_dropped(tmp_path):
    """Forward-compat: unrecognized [tool.newb] keys are silently
    ignored so old newb doesn't crash on new config keys."""
    # Arrange
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import merged_defaults

    (tmp_path / "pyproject.toml").write_text(
        "[tool.newb]\n"
        'template = "python-package"\n'
        'future_feature = "value"\n'  # unknown key
    )
    # Act
    out = merged_defaults(tmp_path)
    # Assert
    assert "future_feature" not in out and out["template"] == "python-package"
