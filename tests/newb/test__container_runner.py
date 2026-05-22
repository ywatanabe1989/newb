"""Argv-shape tests for DockerRunner / PodmanRunner / ApptainerRunner.

These tests do NOT spin up real containers. Instead of mocking
``shutil.which``, they install a REAL fake ``docker`` / ``apptainer``
executable into a tmp ``bin/`` on ``$PATH`` so ``shutil.which`` resolves
it for real, then inspect the argv that ``_build_argv`` would hand to
``subprocess.run``. The point is to catch host/container path mismatches
(the kind that produced the v0.10.0 'Working directory does not exist:
/work/skills' break).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest


@pytest.fixture
def fake_runtime(env_set, tmp_path):
    """Make `docker`/`apptainer` resolvable on PATH via a real shim
    executable, opt newb in via ``NEWB_ANTHROPIC_API_KEY``, and re-root
    HOME to a hermetic tmpdir (so the developer's real
    ``~/.claude/.credentials.json`` can't alter the bind-mount argv).

    Returns the staged package source dir.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("docker", "podman", "apptainer"):
        shim = bin_dir / name
        shim.write_text("#!/bin/sh\nexit 0\n")
        shim.chmod(shim.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    env_set("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    env_set("NEWB_ANTHROPIC_API_KEY", "sk-ant-api03-TEST")
    home = tmp_path / "home"
    home.mkdir()
    env_set("HOME", str(home))

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "README.md").write_text("# pkg\n")
    return src


def test_default_image_uses_ghcr_registry():
    # Arrange
    from newb._container_runner import _default_image

    # Act
    img = _default_image()
    # Assert
    assert img.startswith("ghcr.io/ywatanabe1989/newb-runner:")


def test_default_image_pins_to_current_newb_version():
    # Arrange
    import newb
    from newb._container_runner import _default_image

    # Act
    img = _default_image()
    # Assert
    assert img.endswith(f":{newb.__version__}")


def test_default_image_never_pins_latest():
    # Arrange
    from newb._container_runner import _default_image

    # Act
    img = _default_image()
    # Assert
    assert ":latest" not in img


def test_docker_argv_mounts_project_at_correct_container_path(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        project_mount = next(a for a in argv if a.endswith(":/work/project"))
        _, _, container_part = project_mount.partition(":")
        # Assert
        assert container_part == "/work/project"
    finally:
        r.close()


def test_docker_argv_mounts_project_read_write(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        project_mount = next(a for a in argv if a.endswith(":/work/project"))
        # Assert
        assert ":ro" not in project_mount
    finally:
        r.close()


def test_docker_argv_project_mount_host_part_is_a_real_dir(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        project_mount = next(a for a in argv if a.endswith(":/work/project"))
        host_part, _, _ = project_mount.partition(":")
        # Assert
        assert os.path.isdir(host_part)
    finally:
        r.close()


def test_docker_argv_forwards_newb_api_key_verbatim(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    finally:
        r.close()


def test_docker_argv_does_not_inject_upstream_api_key(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert not any(a.startswith("ANTHROPIC_API_KEY=") for a in argv), argv
    finally:
        r.close()


def test_docker_argv_skips_credentials_mount_when_host_has_none(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert not any(":/home/newb/.claude/.credentials.json" in a for a in argv), argv
    finally:
        r.close()


def test_docker_argv_mounts_credentials_when_host_has_them(fake_runtime, tmp_path):
    # Arrange
    from newb._container_runner import DockerRunner

    creds = tmp_path / "home" / ".claude" / ".credentials.json"
    creds.parent.mkdir(parents=True)
    creds.write_text('{"claudeAiOauth": {"accessToken": "sk-ant-oat01-x"}}')

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        host_part, _, _ = mount.partition(":")
        # Assert
        assert host_part == str(creds)
    finally:
        r.close()


def test_docker_argv_materialises_credentials_from_env_var(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    body = '{"claudeAiOauth": {"accessToken": "sk-ant-oat01-from-env"}}'
    env_set("NEWB_CLAUDE_CODE_CREDENTIALS_JSON", body)

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        host_file = Path(mount.partition(":")[0])
        # Assert
        assert host_file.read_text() == body
    finally:
        r.close()


def test_docker_credentials_tempfile_is_world_readable(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    body = '{"claudeAiOauth": {"accessToken": "sk-ant-oat01-from-env"}}'
    env_set("NEWB_CLAUDE_CODE_CREDENTIALS_JSON", body)

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        host_file = Path(mount.partition(":")[0])
        # Act
        mode = host_file.stat().st_mode & 0o777
        # Assert
        assert mode == 0o644
    finally:
        r.close()


def test_docker_credentials_tempfile_unlinked_on_close(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    body = '{"claudeAiOauth": {"accessToken": "sk-ant-oat01-from-env"}}'
    env_set("NEWB_CLAUDE_CODE_CREDENTIALS_JSON", body)
    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    mount = next(
        a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
    )
    host_file = Path(mount.partition(":")[0])
    # Act
    r.close()
    # Assert
    assert not host_file.exists()


def test_env_var_credentials_take_precedence_over_host_file(
    env_set, fake_runtime, tmp_path
):
    # Arrange
    from newb._container_runner import DockerRunner

    host_creds = tmp_path / "home" / ".claude" / ".credentials.json"
    host_creds.parent.mkdir(parents=True)
    host_creds.write_text('{"claudeAiOauth": {"accessToken": "from-host-file"}}')
    env_set(
        "NEWB_CLAUDE_CODE_CREDENTIALS_JSON",
        '{"claudeAiOauth": {"accessToken": "from-env-var"}}',
    )

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        # Act
        host_part = Path(mount.partition(":")[0])
        # Assert
        assert "from-env-var" in host_part.read_text()
    finally:
        r.close()


def test_docker_argv_uses_versioned_image_by_default(fake_runtime):
    # Arrange
    import newb
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        image_tag = argv[-1]
        # Assert
        assert image_tag.endswith(f":{newb.__version__}"), image_tag
    finally:
        r.close()


def test_oauth_token_passes_through_opaquely(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    env_set("NEWB_ANTHROPIC_API_KEY", "sk-ant-oat01-TEST")

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-oat01-TEST" for a in argv), argv
    finally:
        r.close()


def test_missing_newb_api_key_raises_clearly(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    # Wipe the opt-in key; set the upstream one to prove no fallback.
    os.environ.pop("NEWB_ANTHROPIC_API_KEY", None)
    env_set("ANTHROPIC_API_KEY", "sk-ant-api03-LEAK-FROM-SHELL")
    # Act
    ctx = pytest.raises(RuntimeError, match=r"NEWB_ANTHROPIC_API_KEY")
    # Assert
    with ctx:
        DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)


def test_docker_argv_includes_cap_drop_by_default(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--cap-drop=ALL" in argv
    finally:
        r.close()


def test_docker_argv_includes_no_new_privileges_by_default(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--security-opt=no-new-privileges" in argv
    finally:
        r.close()


def test_docker_argv_uses_bridge_network_by_default(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--network=bridge" in argv
    finally:
        r.close()


def test_docker_argv_omits_resource_caps_by_default(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        capped = [
            a for a in argv if a.startswith(("--memory=", "--cpus=", "--pids-limit="))
        ]
        # Assert
        assert capped == [], argv
    finally:
        r.close()


def test_docker_argv_memory_cap_via_env(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    env_set("NEWB_HARDEN_MEMORY", "4g")
    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--memory=4g" in argv
    finally:
        r.close()


def test_docker_argv_cpu_cap_via_env(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    env_set("NEWB_HARDEN_CPUS", "2")
    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--cpus=2" in argv
    finally:
        r.close()


def test_docker_argv_pids_cap_via_env(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    env_set("NEWB_HARDEN_PIDS_LIMIT", "256")
    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--pids-limit=256" in argv
    finally:
        r.close()


def test_docker_argv_no_network_via_env(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    env_set("NEWB_HARDEN_NO_NETWORK", "1")
    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert "--network=none" in argv
    finally:
        r.close()


def test_podman_argv_uses_podman_binary(fake_runtime):
    # Arrange
    from newb._container_runner import PodmanRunner

    podman = PodmanRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = podman._build_argv()
        # Act
        # Assert
        assert argv[0] == "podman"
    finally:
        podman.close()


def test_podman_argv_keeps_docker_hardening_shape(fake_runtime):
    # Arrange
    from newb._container_runner import PodmanRunner

    podman = PodmanRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = podman._build_argv()
        # Act
        flags = {
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--network=bridge",
        }
        # Assert
        assert flags.issubset(set(argv))
    finally:
        podman.close()


def test_podman_argv_forwards_newb_api_key(fake_runtime):
    # Arrange
    from newb._container_runner import PodmanRunner

    podman = PodmanRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = podman._build_argv()
        # Act
        # Assert
        assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv)
    finally:
        podman.close()


def test_apptainer_argv_forwards_memory_cap(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import ApptainerRunner

    env_set("NEWB_HARDEN_MEMORY", "4g")
    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        value = argv[argv.index("--memory") + 1]
        # Assert
        assert value == "4g"
    finally:
        r.close()


def test_apptainer_argv_forwards_cpu_cap(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import ApptainerRunner

    env_set("NEWB_HARDEN_CPUS", "2")
    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        value = argv[argv.index("--cpus") + 1]
        # Assert
        assert value == "2"
    finally:
        r.close()


def test_apptainer_argv_forwards_pids_cap(env_set, fake_runtime):
    # Arrange
    from newb._container_runner import ApptainerRunner

    env_set("NEWB_HARDEN_PIDS_LIMIT", "256")
    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        value = argv[argv.index("--pids-limit") + 1]
        # Assert
        assert value == "256"
    finally:
        r.close()


def test_apptainer_argv_mounts_project_at_correct_path(fake_runtime):
    # Arrange
    from newb._container_runner import ApptainerRunner

    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        project_bind = next(a for a in argv if a.endswith(":/work/project"))
        _, _, container_part = project_bind.partition(":")
        # Assert
        assert container_part == "/work/project"
    finally:
        r.close()


def test_apptainer_argv_forwards_newb_api_key(fake_runtime):
    # Arrange
    from newb._container_runner import ApptainerRunner

    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    finally:
        r.close()


def test_docker_argv_mounts_pip_cache_when_configured(fake_runtime, tmp_path):
    # Arrange
    from newb._container_runner import DockerRunner

    cache = tmp_path / "newb-pip"
    r = DockerRunner(
        skills_mount=fake_runtime,
        project_root=fake_runtime,
        pip_cache_dir=str(cache),
    )
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert any(f"{cache}:/home/newb/.cache/pip" == a for a in argv), argv
    finally:
        r.close()


def test_docker_argv_omits_pip_cache_when_unset(fake_runtime):
    # Arrange
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    try:
        argv = r._build_argv()
        # Act
        # Assert
        assert not any("/home/newb/.cache/pip" in a for a in argv), argv
    finally:
        r.close()
