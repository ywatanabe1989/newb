"""Tests for newb._pyproject_config — `[tool.newb]` defaults."""

from __future__ import annotations

import pytest


def test_missing_pyproject_returns_empty(tmp_path):
    from newb._pyproject_config import load_pyproject_config

    assert load_pyproject_config(tmp_path) == {}


def test_pyproject_without_tool_newb_returns_empty(tmp_path):
    from newb._pyproject_config import load_pyproject_config

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "0.0.0"\n'
    )
    assert load_pyproject_config(tmp_path) == {}


def test_pyproject_tool_newb_parsed(tmp_path):
    """[tool.newb] section is read into a dict."""
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import load_pyproject_config

    (tmp_path / "pyproject.toml").write_text(
        "[tool.newb]\n"
        'template = "cli-tool"\n'
        'runtime = "podman"\n'
        'scope = "docs"\n'
        "runs = 3\n"
    )
    cfg = load_pyproject_config(tmp_path)
    assert cfg["template"] == "cli-tool"
    assert cfg["runtime"] == "podman"
    assert cfg["scope"] == "docs"
    assert cfg["runs"] == 3


def test_pyproject_walks_up_to_find_config(tmp_path):
    """If `start` is a sub-dir, walk up to find pyproject.toml."""
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import load_pyproject_config

    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\nmodel = "claude-haiku-4-5"\n'
    )
    sub = tmp_path / "src" / "mypkg"
    sub.mkdir(parents=True)
    cfg = load_pyproject_config(sub)
    assert cfg["model"] == "claude-haiku-4-5"


def test_merged_defaults_cli_overrides_pyproject(tmp_path):
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import merged_defaults

    (tmp_path / "pyproject.toml").write_text(
        '[tool.newb]\ntemplate = "python-package"\nruntime = "podman"\n'
    )
    # CLI passed --runtime docker; --template not set (None).
    out = merged_defaults(tmp_path, runtime="docker", template=None)
    assert out["runtime"] == "docker"  # CLI wins
    assert out["template"] == "python-package"  # pyproject preserved


def test_merged_defaults_unknown_keys_dropped(tmp_path):
    """Forward-compat: unrecognized [tool.newb] keys are silently
    ignored so old newb doesn't crash on new config keys."""
    pytest.importorskip("tomllib", reason="needs tomllib (py3.11+) or tomli")
    from newb._pyproject_config import merged_defaults

    (tmp_path / "pyproject.toml").write_text(
        "[tool.newb]\n"
        'template = "python-package"\n'
        'future_feature = "value"\n'  # unknown key
    )
    out = merged_defaults(tmp_path)
    assert "future_feature" not in out
    assert out["template"] == "python-package"
