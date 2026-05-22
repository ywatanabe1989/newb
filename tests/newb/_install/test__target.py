"""Tests for newb._install_target.resolve_target."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from newb._install._target import resolve_target


def _git_init(path: Path, remote: str | None = None) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if remote:
        subprocess.run(
            ["git", "-C", str(path), "remote", "add", "origin", remote],
            check=True,
        )


def test_explicit_owner_repo_passthrough():
    # Arrange
    spec = "ywatanabe1989/newb"
    # Act
    out = resolve_target(spec)
    # Assert
    assert out == "ywatanabe1989/newb"


def test_dot_reads_current_git_remote(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "git@github.com:owner/repo.git")
    # Act
    out = resolve_target(".", cwd=tmp_path)
    # Assert
    assert out == "owner/repo"


def test_none_reads_current_git_remote(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "https://github.com/owner/repo.git")
    # Act
    out = resolve_target(None, cwd=tmp_path)
    # Assert
    assert out == "owner/repo"


def test_https_remote_without_dotgit_suffix_is_parsed(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "https://github.com/owner/repo")
    # Act
    out = resolve_target(".", cwd=tmp_path)
    # Assert
    assert out == "owner/repo"


def test_no_git_remote_raises(tmp_path: Path):
    # Arrange
    _git_init(tmp_path)
    # Act
    ctx = pytest.raises(ValueError, match="no git remote")
    # Assert
    with ctx:
        resolve_target(".", cwd=tmp_path)


def test_non_github_remote_raises(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "git@gitlab.com:owner/repo.git")
    # Act
    ctx = pytest.raises(ValueError, match="doesn't look like a GitHub URL")
    # Assert
    with ctx:
        resolve_target(".", cwd=tmp_path)


def test_malformed_owner_repo_raises():
    # Arrange
    spec = "not-a-repo-spec"
    # Act
    ctx = pytest.raises(ValueError, match="not in <owner>/<repo>")
    # Assert
    with ctx:
        resolve_target(spec)


def test_owner_repo_with_dots_and_dashes_passes_through():
    # Arrange
    # "owner.with.dots" isn't valid GitHub username, but "repo.with.dots" is.
    spec = "owner-1/repo.x_y"
    # Act
    out = resolve_target(spec)
    # Assert
    assert out == "owner-1/repo.x_y"


# EOF
