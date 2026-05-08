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
    assert resolve_target("ywatanabe1989/newb") == "ywatanabe1989/newb"


def test_dot_reads_current_git_remote(tmp_path: Path):
    _git_init(tmp_path, "git@github.com:owner/repo.git")
    assert resolve_target(".", cwd=tmp_path) == "owner/repo"


def test_none_reads_current_git_remote(tmp_path: Path):
    _git_init(tmp_path, "https://github.com/owner/repo.git")
    assert resolve_target(None, cwd=tmp_path) == "owner/repo"


def test_https_no_dotgit(tmp_path: Path):
    _git_init(tmp_path, "https://github.com/owner/repo")
    assert resolve_target(".", cwd=tmp_path) == "owner/repo"


def test_no_git_remote_raises(tmp_path: Path):
    _git_init(tmp_path)
    with pytest.raises(ValueError, match="no git remote"):
        resolve_target(".", cwd=tmp_path)


def test_non_github_remote_raises(tmp_path: Path):
    _git_init(tmp_path, "git@gitlab.com:owner/repo.git")
    with pytest.raises(ValueError, match="doesn't look like a GitHub URL"):
        resolve_target(".", cwd=tmp_path)


def test_malformed_owner_repo_raises():
    with pytest.raises(ValueError, match="not in <owner>/<repo>"):
        resolve_target("not-a-repo-spec")


def test_owner_repo_with_dots_and_dashes():
    # "owner.with.dots" isn't valid GitHub username, but "repo.with.dots" is.
    assert resolve_target("owner-1/repo.x_y") == "owner-1/repo.x_y"


# EOF
