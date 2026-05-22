"""Tests for newb._install._target.resolve_target."""

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
    resolved = resolve_target(spec)
    # Assert
    assert resolved == "ywatanabe1989/newb"


def test_dot_reads_current_git_remote_ssh(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "git@github.com:owner/repo.git")
    # Act
    resolved = resolve_target(".", cwd=tmp_path)
    # Assert
    assert resolved == "owner/repo"


def test_none_reads_current_git_remote_https(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "https://github.com/owner/repo.git")
    # Act
    resolved = resolve_target(None, cwd=tmp_path)
    # Assert
    assert resolved == "owner/repo"


def test_https_remote_without_dotgit_suffix(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "https://github.com/owner/repo")
    # Act
    resolved = resolve_target(".", cwd=tmp_path)
    # Assert
    assert resolved == "owner/repo"


def test_no_git_remote_raises(tmp_path: Path):
    # Arrange
    _git_init(tmp_path)
    ctx = pytest.raises(ValueError, match="no git remote")
    # Act
    # Assert
    with ctx:
        resolve_target(".", cwd=tmp_path)


def test_non_github_remote_raises(tmp_path: Path):
    # Arrange
    _git_init(tmp_path, "git@gitlab.com:owner/repo.git")
    ctx = pytest.raises(ValueError, match="doesn't look like a GitHub URL")
    # Act
    # Assert
    with ctx:
        resolve_target(".", cwd=tmp_path)


def test_malformed_owner_repo_raises():
    # Arrange
    ctx = pytest.raises(ValueError, match="not in <owner>/<repo>")
    # Act
    # Assert
    with ctx:
        resolve_target("not-a-repo-spec")


def test_owner_repo_with_dots_and_dashes_passthrough():
    # Arrange
    spec = "owner-1/repo.x_y"
    # Act
    resolved = resolve_target(spec)
    # Assert
    assert resolved == "owner-1/repo.x_y"
