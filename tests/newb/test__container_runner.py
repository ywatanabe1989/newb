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
    """Pretend `docker` / `apptainer` exist on PATH and the API key is set."""
    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/fake")
    monkeypatch.setenv("NEWB_ANTHROPIC_API_KEY", "sk-ant-api03-TEST")
    # Build a minimal source dir so stage_project succeeds.
    src = tmp_path / "pkg"
    src.mkdir()
    (src / "README.md").write_text("# pkg\n")
    return src


def test_default_image_pins_to_current_newb_version():
    """The default image tag is `:<newb_version>` — never `:latest`.

    A stale local `:latest` from an earlier install must NOT silently
    mismatch the host code. Pin to the version that ships with this
    newb so the host/container interfaces always match.
    """
    import newb
    from newb._container_runner import _default_image

    img = _default_image()
    assert img.startswith("ghcr.io/ywatanabe1989/newb-runner:")
    assert img.endswith(f":{newb.__version__}")
    assert ":latest" not in img


def test_docker_argv_mounts_project_at_correct_path(fake_runtime):
    """DockerRunner builds argv with -v <staged>:/work/project (read-write).

    Catches the regression where /work/skills (old) and /work/project
    (current) drift apart between host and container.
    """
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("hello")

    # Find the -v flag and inspect its argument.
    v_idx = argv.index("-v")
    mount_spec = argv[v_idx + 1]
    host_part, _, container_part = mount_spec.partition(":")
    assert container_part == "/work/project", (
        f"docker mount must be /work/project, got {container_part!r} "
        "(would produce 'Working directory does not exist' inside the container)"
    )
    # rw mount (no `:ro`) — the agent needs to `pip install -e .`
    assert ":ro" not in mount_spec
    assert os.path.isdir(host_part)
    r.close()


def test_docker_argv_passes_anthropic_api_key_through(fake_runtime):
    """NEWB_ANTHROPIC_API_KEY is forwarded as ANTHROPIC_API_KEY into the container."""
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    assert any(a == "ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    r.close()


def test_docker_argv_uses_versioned_image_by_default(fake_runtime):
    """The trailing image tag is the versioned one, not :latest."""
    import newb
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    image_tag = argv[-2]  # second-to-last (last is the prompt)
    assert image_tag.endswith(f":{newb.__version__}"), image_tag
    r.close()


def test_oauth_key_routed_via_credentials_mount_not_env(
    monkeypatch, fake_runtime, tmp_path
):
    """OAuth tokens (sk-ant-oat...) must NOT go in as ANTHROPIC_API_KEY env.

    The bundled Claude CLI inside the container rejects OAuth tokens
    presented as API keys. Right path: bind-mount
    ~/.claude/.credentials.json into the container at the agent's
    home AND set NEWB_AUTH_MODE=oauth so runner.py's auth guard
    doesn't reject. This was the silent break behind the v0.10.0
    'Command failed with exit code 1' on Pro/Max-subscriber laptops.
    """
    from newb._container_runner import DockerRunner

    monkeypatch.delenv("NEWB_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("NEWB_ANTHROPIC_API_KEY_OAUTH", "sk-ant-oat01-TEST")

    fake_home = tmp_path / "home"
    (fake_home / ".claude").mkdir(parents=True)
    (fake_home / ".claude" / ".credentials.json").write_text('{"x": 1}')
    monkeypatch.setenv("HOME", str(fake_home))

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")

    assert not any("ANTHROPIC_API_KEY=sk-ant-oat" in a for a in argv), (
        "OAuth token leaked into ANTHROPIC_API_KEY env — the bundled "
        "CLI will reject it. Use the credentials.json mount instead."
    )
    assert any(":/home/newb/.claude/.credentials.json:ro" in a for a in argv), (
        f"OAuth credentials mount missing from argv: {argv}"
    )
    assert "NEWB_AUTH_MODE=oauth" in argv
    r.close()


def test_api_key_uses_env_var_not_credentials_mount(
    monkeypatch, fake_runtime, tmp_path
):
    """Real API keys (sk-ant-api03-...) go in as ANTHROPIC_API_KEY env;
    the credentials.json mount is NOT added.
    """
    from newb._container_runner import DockerRunner

    monkeypatch.setenv("NEWB_ANTHROPIC_API_KEY", "sk-ant-api03-TEST")
    monkeypatch.delenv("NEWB_ANTHROPIC_API_KEY_OAUTH", raising=False)

    fake_home = tmp_path / "home"
    (fake_home / ".claude").mkdir(parents=True)
    (fake_home / ".claude" / ".credentials.json").write_text('{"x": 1}')
    monkeypatch.setenv("HOME", str(fake_home))

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")

    assert any(a == "ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    assert not any(":/home/newb/.claude/.credentials.json" in a for a in argv)
    assert "NEWB_AUTH_MODE=oauth" not in argv
    r.close()


def test_apptainer_argv_mounts_project_at_correct_path(fake_runtime):
    """ApptainerRunner mirrors DockerRunner's mount semantics."""
    from newb._container_runner import ApptainerRunner

    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv("x")
    bind_idx = argv.index("--bind")
    bind_spec = argv[bind_idx + 1]
    host_part, _, container_part = bind_spec.partition(":")
    assert container_part == "/work/project"
    assert ":ro" not in bind_spec
    r.close()
