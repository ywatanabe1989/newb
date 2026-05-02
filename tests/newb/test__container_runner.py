"""End-to-end shape tests for DockerRunner / ApptainerRunner.

These tests do NOT spin up real containers — they monkeypatch
``shutil.which`` so the constructor accepts a missing binary, and
inspect the argv that would be sent to ``subprocess.run``. The point
is to catch host/container path mismatches (the kind that produced
the v0.10.0 'Working directory does not exist: /work/skills' break).
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def fake_runtime(monkeypatch, tmp_path):
    """Pretend `docker`/`apptainer` exist on PATH and opt newb in
    via the single ``NEWB_ANTHROPIC_API_KEY`` env var."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setenv("NEWB_ANTHROPIC_API_KEY", "sk-ant-api03-TEST")

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "README.md").write_text("# pkg\n")
    return src


def test_default_image_pins_to_current_newb_version():
    import newb
    from newb._container_runner import _default_image

    img = _default_image()
    assert img.startswith("ghcr.io/ywatanabe1989/newb-runner:")
    assert img.endswith(f":{newb.__version__}")
    assert ":latest" not in img


def test_docker_argv_mounts_project_at_correct_path(fake_runtime):
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("hello")

    project_mount = next(a for a in argv if a.endswith(":/work/project"))
    host_part, _, container_part = project_mount.partition(":")
    assert container_part == "/work/project"
    assert ":ro" not in project_mount
    assert os.path.isdir(host_part)
    r.close()


def test_docker_argv_forwards_newb_api_key_only(fake_runtime):
    """DockerRunner forwards NEWB_ANTHROPIC_API_KEY into the container
    verbatim. It must NOT inject ANTHROPIC_API_KEY (the upstream name)
    — that's the in-container runner.py's job, decided by token
    prefix (sk-ant-api* vs sk-ant-oat*)."""
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    assert not any(a.startswith("ANTHROPIC_API_KEY=") for a in argv), argv
    # No credentials.json mount — the env-var path keeps newb usable in CI.
    assert not any(":/home/newb/.claude/.credentials.json" in a for a in argv), argv
    r.close()


def test_docker_argv_uses_versioned_image_by_default(fake_runtime):
    import newb
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    image_tag = argv[-2]
    assert image_tag.endswith(f":{newb.__version__}"), image_tag
    r.close()


def test_oauth_token_passes_through_opaquely(monkeypatch, fake_runtime):
    """OAuth tokens (sk-ant-oat*) pass through verbatim. Host runner
    does not inspect token shape — that's the in-container runner.py."""
    from newb._container_runner import DockerRunner

    monkeypatch.setenv("NEWB_ANTHROPIC_API_KEY", "sk-ant-oat01-TEST")

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-oat01-TEST" for a in argv), argv
    assert not any(a.startswith("ANTHROPIC_API_KEY=") for a in argv), argv
    r.close()


def test_missing_newb_api_key_raises_clearly(monkeypatch, fake_runtime):
    """Constructor must fail loud when NEWB_ANTHROPIC_API_KEY is unset
    — no silent fallback to the upstream ANTHROPIC_API_KEY env var."""
    from newb._container_runner import DockerRunner

    monkeypatch.delenv("NEWB_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-LEAK-FROM-SHELL")

    with pytest.raises(RuntimeError, match=r"NEWB_ANTHROPIC_API_KEY"):
        DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)


def test_apptainer_argv_mounts_project_and_forwards_token(fake_runtime):
    """ApptainerRunner mirrors DockerRunner: project bind-mount
    read-write, token forwarded as NEWB_ANTHROPIC_API_KEY env."""
    from newb._container_runner import ApptainerRunner

    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    project_bind = next(a for a in argv if a.endswith(":/work/project"))
    _, _, container_part = project_bind.partition(":")
    assert container_part == "/work/project"
    assert ":ro" not in project_bind
    assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    assert not any(a.startswith("ANTHROPIC_API_KEY=") for a in argv), argv
    r.close()
