"""End-to-end shape tests for DockerRunner / ApptainerRunner.

These tests do NOT spin up real containers — they inject a fake
``which`` callable so the constructor accepts a missing runtime
binary, and inspect the argv that would be sent to ``subprocess.run``.
The point is to catch host/container path mismatches (the kind that
produced the v0.10.0 'Working directory does not exist: /work/skills'
break).

No mocks (PA-306): env-var mutations go through the ``env_save_restore``
yield fixture; ``shutil.which`` is injected via the ``which=`` kwarg
on the runner constructor rather than patched.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _always_found(_binary: str) -> str:
    """Inject this as ``which=`` to pretend any runtime binary is on PATH."""
    return "/usr/bin/fake"


@pytest.fixture
def fake_runtime(env_save_restore, tmp_path):
    """Pretend ``docker``/``apptainer`` exist on PATH and opt newb in
    via the single ``NEWB_ANTHROPIC_API_KEY`` env var. Re-roots HOME
    to a tmpdir so tests are hermetic w.r.t. the developer's actual
    ``~/.claude/.credentials.json`` (which would otherwise alter the
    bind-mount argv).

    Returns the staged project src dir.
    """
    env_save_restore("NEWB_ANTHROPIC_API_KEY", "sk-ant-api03-TEST")
    env_save_restore("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()

    src = tmp_path / "pkg"
    src.mkdir()
    (src / "README.md").write_text("# pkg\n")
    return src


# ---------------------------------------------------------------------------
# _default_image — 3 facets split.
# ---------------------------------------------------------------------------


@pytest.fixture
def _default_image_tag() -> str:
    from newb._container_runner import _default_image

    return _default_image()


def test_default_image_starts_with_canonical_ghcr_prefix(_default_image_tag):
    # Arrange
    img = _default_image_tag
    # Act
    starts = img.startswith("ghcr.io/ywatanabe1989/newb-runner:")
    # Assert
    assert starts


def test_default_image_ends_with_current_newb_version(_default_image_tag):
    # Arrange
    import newb

    img = _default_image_tag
    # Act
    ends = img.endswith(f":{newb.__version__}")
    # Assert
    assert ends


def test_default_image_does_not_carry_latest_tag(_default_image_tag):
    # Arrange
    img = _default_image_tag
    # Act
    present = ":latest" in img
    # Assert
    assert present is False


# ---------------------------------------------------------------------------
# Helper fixtures: a freshly-built DockerRunner's argv, for shared Arrange.
# ---------------------------------------------------------------------------


@pytest.fixture
def docker_argv(fake_runtime):
    """Build argv for a default DockerRunner; ensure cleanup via the runner's
    own close() method via finalizer."""
    from newb._container_runner import DockerRunner

    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_docker_argv_project_mount_container_path_is_work_project(docker_argv):
    # Arrange
    argv = docker_argv
    project_mount = next(a for a in argv if a.endswith(":/work/project"))
    _, _, container_part = project_mount.partition(":")
    # Act
    value = container_part
    # Assert
    assert value == "/work/project"


def test_docker_argv_project_mount_is_read_write(docker_argv):
    # Arrange
    argv = docker_argv
    project_mount = next(a for a in argv if a.endswith(":/work/project"))
    # Act
    has_ro = ":ro" in project_mount
    # Assert
    assert has_ro is False


def test_docker_argv_project_mount_host_path_is_existing_dir(docker_argv):
    # Arrange
    argv = docker_argv
    project_mount = next(a for a in argv if a.endswith(":/work/project"))
    host_part, _, _ = project_mount.partition(":")
    # Act
    is_dir = os.path.isdir(host_part)
    # Assert
    assert is_dir


def test_docker_argv_forwards_newb_api_key(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    forwarded = any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv)
    # Assert
    assert forwarded, argv


def test_docker_argv_does_not_forward_upstream_api_key(docker_argv):
    """Must NOT inject ANTHROPIC_API_KEY (the upstream name) — that's the
    in-container runner.py's job, decided by token prefix."""
    # Arrange
    argv = docker_argv
    # Act
    leaked = any(a.startswith("ANTHROPIC_API_KEY=") for a in argv)
    # Assert
    assert leaked is False, argv


def test_docker_argv_no_credentials_bind_when_host_empty(docker_argv):
    """With no ``~/.claude/.credentials.json`` on the host (the fake
    HOME from the fixture is empty), no bind-mount should appear —
    the env-var-only path keeps newb usable in CI when the runner
    has only a real ``sk-ant-api*`` key.
    """
    # Arrange
    argv = docker_argv
    # Act
    present = any(":/home/newb/.claude/.credentials.json" in a for a in argv)
    # Assert
    assert present is False, argv


def test_docker_argv_mounts_credentials_when_host_has_them(fake_runtime, tmp_path):
    """When ``~/.claude/.credentials.json`` exists on the host,
    DockerRunner bind-mounts it read-only into the container at
    ``/home/newb/.claude/.credentials.json``."""
    # Arrange
    from newb._container_runner import DockerRunner

    creds = tmp_path / "home" / ".claude" / ".credentials.json"
    creds.parent.mkdir(parents=True)
    creds.write_text('{"claudeAiOauth": {"accessToken": "sk-ant-oat01-x"}}')
    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        argv = r._build_argv()
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        host_part, _, _ = mount.partition(":")
        # Act
        value = host_part
        # Assert
        assert value == str(creds)
    finally:
        r.close()


# ---------------------------------------------------------------------------
# Tempfile materialisation from $NEWB_CLAUDE_CODE_CREDENTIALS_JSON.
# ---------------------------------------------------------------------------


@pytest.fixture
def _env_creds_materialised(env_save_restore, fake_runtime):
    """Stand up a DockerRunner with the env-var credentials path active,
    inspect argv, then close(); yield (mount_token, body, host_file_after_close).
    """
    from newb._container_runner import DockerRunner

    body = '{"claudeAiOauth": {"accessToken": "sk-ant-oat01-from-env"}}'
    env_save_restore("NEWB_CLAUDE_CODE_CREDENTIALS_JSON", body)

    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        argv = r._build_argv()
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        host_part, _, _ = mount.partition(":")
        host_file = Path(host_part)
        info = {
            "is_file": host_file.is_file(),
            "text": host_file.read_text(),
            "mode": host_file.stat().st_mode & 0o777,
            "path": host_file,
        }
    finally:
        r.close()
    info["exists_after_close"] = info["path"].exists()
    info["body"] = body
    return info


def test_env_var_creds_materialise_to_real_file(_env_creds_materialised):
    # Arrange
    info = _env_creds_materialised
    # Act
    was_file = info["is_file"]
    # Assert
    assert was_file


def test_env_var_creds_tempfile_contents_equal_env_var(_env_creds_materialised):
    # Arrange
    info = _env_creds_materialised
    # Act
    contents = info["text"]
    # Assert
    assert contents == info["body"]


def test_env_var_creds_tempfile_mode_is_644(_env_creds_materialised):
    """0644 so the container's `newb` UID can read across UID gaps."""
    # Arrange
    info = _env_creds_materialised
    # Act
    mode = info["mode"]
    # Assert
    assert mode == 0o644


def test_env_var_creds_tempfile_unlinked_on_close(_env_creds_materialised):
    """close() unlinks the tempfile."""
    # Arrange
    info = _env_creds_materialised
    # Act
    present = info["exists_after_close"]
    # Assert
    assert present is False


# ---------------------------------------------------------------------------
# Precedence — env-var wins over host file.
# ---------------------------------------------------------------------------


@pytest.fixture
def _env_vs_host_precedence(env_save_restore, fake_runtime, tmp_path):
    from newb._container_runner import DockerRunner

    host_creds = tmp_path / "home" / ".claude" / ".credentials.json"
    host_creds.parent.mkdir(parents=True)
    host_creds.write_text('{"claudeAiOauth": {"accessToken": "from-host-file"}}')
    env_save_restore(
        "NEWB_CLAUDE_CODE_CREDENTIALS_JSON",
        '{"claudeAiOauth": {"accessToken": "from-env-var"}}',
    )
    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        argv = r._build_argv()
        mount = next(
            a for a in argv if a.endswith(":/home/newb/.claude/.credentials.json:ro")
        )
        host_part, _, _ = mount.partition(":")
        info = {
            "host_creds": host_creds,
            "mounted_path": Path(host_part),
            "mounted_text": Path(host_part).read_text(),
        }
    finally:
        r.close()
    return info


def test_env_var_creds_path_is_not_host_creds_path(_env_vs_host_precedence):
    # Arrange
    info = _env_vs_host_precedence
    # Act
    same = info["mounted_path"] == info["host_creds"]
    # Assert
    assert same is False


def test_env_var_creds_mounted_contents_are_env_var_body(_env_vs_host_precedence):
    # Arrange
    info = _env_vs_host_precedence
    # Act
    present = "from-env-var" in info["mounted_text"]
    # Assert
    assert present


def test_docker_argv_uses_versioned_image_by_default(docker_argv):
    # Arrange
    import newb

    argv = docker_argv
    image_tag = argv[-1]
    # Act
    suffix = image_tag.endswith(f":{newb.__version__}")
    # Assert
    assert suffix, image_tag


# ---------------------------------------------------------------------------
# OAuth token pass-through.
# ---------------------------------------------------------------------------


@pytest.fixture
def _oauth_token_argv(env_save_restore, fake_runtime):
    from newb._container_runner import DockerRunner

    env_save_restore("NEWB_ANTHROPIC_API_KEY", "sk-ant-oat01-TEST")
    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_oauth_token_forwarded_verbatim_to_newb_api_key(_oauth_token_argv):
    """Host runner does not inspect token shape — that's the in-container
    runner.py."""
    # Arrange
    argv = _oauth_token_argv
    # Act
    present = any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-oat01-TEST" for a in argv)
    # Assert
    assert present, argv


def test_oauth_token_does_not_forward_upstream_api_key(_oauth_token_argv):
    # Arrange
    argv = _oauth_token_argv
    # Act
    leaked = any(a.startswith("ANTHROPIC_API_KEY=") for a in argv)
    # Assert
    assert leaked is False, argv


def test_missing_newb_api_key_raises_clearly(env_save_restore, fake_runtime):
    """Constructor must fail loud when NEWB_ANTHROPIC_API_KEY is unset
    — no silent fallback to the upstream ANTHROPIC_API_KEY env var."""
    # Arrange
    from newb._container_runner import DockerRunner

    env_save_restore("NEWB_ANTHROPIC_API_KEY", None)
    env_save_restore("ANTHROPIC_API_KEY", "sk-ant-api03-LEAK-FROM-SHELL")
    # Act
    ctx = pytest.raises(RuntimeError, match=r"NEWB_ANTHROPIC_API_KEY")
    # Assert
    with ctx:
        DockerRunner(
            skills_mount=fake_runtime,
            project_root=fake_runtime,
            which=_always_found,
        )


# ---------------------------------------------------------------------------
# Default hardening — boundary-only. Per-flag splits.
# ---------------------------------------------------------------------------


def test_docker_argv_default_hardening_has_cap_drop_all(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    present = "--cap-drop=ALL" in argv
    # Assert
    assert present


def test_docker_argv_default_hardening_has_no_new_privileges(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    present = "--security-opt=no-new-privileges" in argv
    # Assert
    assert present


def test_docker_argv_default_hardening_has_bridge_network(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    present = "--network=bridge" in argv
    # Assert
    assert present


def test_docker_argv_default_hardening_has_no_memory_cap(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    matches = [a for a in argv if a.startswith("--memory=")]
    # Assert
    assert matches == [], argv


def test_docker_argv_default_hardening_has_no_cpus_cap(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    matches = [a for a in argv if a.startswith("--cpus=")]
    # Assert
    assert matches == [], argv


def test_docker_argv_default_hardening_has_no_pids_limit(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    matches = [a for a in argv if a.startswith("--pids-limit=")]
    # Assert
    assert matches == [], argv


# ---------------------------------------------------------------------------
# Resource-cap env vars → docker argv.
# ---------------------------------------------------------------------------


@pytest.fixture
def _docker_argv_with_resource_caps(env_save_restore, fake_runtime):
    from newb._container_runner import DockerRunner

    env_save_restore("NEWB_HARDEN_MEMORY", "4g")
    env_save_restore("NEWB_HARDEN_CPUS", "2")
    env_save_restore("NEWB_HARDEN_PIDS_LIMIT", "256")
    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_docker_argv_resource_caps_via_env_emits_memory(
    _docker_argv_with_resource_caps,
):
    # Arrange
    argv = _docker_argv_with_resource_caps
    # Act
    present = "--memory=4g" in argv
    # Assert
    assert present


def test_docker_argv_resource_caps_via_env_emits_cpus(_docker_argv_with_resource_caps):
    # Arrange
    argv = _docker_argv_with_resource_caps
    # Act
    present = "--cpus=2" in argv
    # Assert
    assert present


def test_docker_argv_resource_caps_via_env_emits_pids_limit(
    _docker_argv_with_resource_caps,
):
    # Arrange
    argv = _docker_argv_with_resource_caps
    # Act
    present = "--pids-limit=256" in argv
    # Assert
    assert present


# ---------------------------------------------------------------------------
# NEWB_HARDEN_NO_NETWORK=1.
# ---------------------------------------------------------------------------


@pytest.fixture
def _docker_argv_no_network(env_save_restore, fake_runtime):
    from newb._container_runner import DockerRunner

    env_save_restore("NEWB_HARDEN_NO_NETWORK", "1")
    r = DockerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_docker_argv_no_network_emits_network_none(_docker_argv_no_network):
    # Arrange
    argv = _docker_argv_no_network
    # Act
    present = "--network=none" in argv
    # Assert
    assert present


def test_docker_argv_no_network_drops_network_bridge(_docker_argv_no_network):
    # Arrange
    argv = _docker_argv_no_network
    # Act
    present = "--network=bridge" in argv
    # Assert
    assert present is False


# ---------------------------------------------------------------------------
# PodmanRunner inherits everything; binary swap is the only diff.
# ---------------------------------------------------------------------------


@pytest.fixture
def _podman_argv(fake_runtime):
    from newb._container_runner import PodmanRunner

    r = PodmanRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_podman_argv_binary_token_is_podman(_podman_argv):
    # Arrange
    argv = _podman_argv
    # Act
    head = argv[0]
    # Assert
    assert head == "podman"


def test_podman_argv_inherits_cap_drop_all(_podman_argv):
    # Arrange
    argv = _podman_argv
    # Act
    present = "--cap-drop=ALL" in argv
    # Assert
    assert present


def test_podman_argv_inherits_no_new_privileges(_podman_argv):
    # Arrange
    argv = _podman_argv
    # Act
    present = "--security-opt=no-new-privileges" in argv
    # Assert
    assert present


def test_podman_argv_inherits_bridge_network(_podman_argv):
    # Arrange
    argv = _podman_argv
    # Act
    present = "--network=bridge" in argv
    # Assert
    assert present


def test_podman_argv_inherits_newb_api_key_forwarding(_podman_argv):
    # Arrange
    argv = _podman_argv
    # Act
    forwarded = any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv)
    # Assert
    assert forwarded


# ---------------------------------------------------------------------------
# ApptainerRunner: --flag value pairs (not --flag=value).
# ---------------------------------------------------------------------------


@pytest.fixture
def _apptainer_argv_with_resource_caps(env_save_restore, fake_runtime):
    from newb._container_runner import ApptainerRunner

    env_save_restore("NEWB_HARDEN_MEMORY", "4g")
    env_save_restore("NEWB_HARDEN_CPUS", "2")
    env_save_restore("NEWB_HARDEN_PIDS_LIMIT", "256")
    r = ApptainerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_apptainer_argv_memory_flag_followed_by_value(
    _apptainer_argv_with_resource_caps,
):
    # Arrange
    argv = _apptainer_argv_with_resource_caps
    # Act
    value = argv[argv.index("--memory") + 1]
    # Assert
    assert value == "4g"


def test_apptainer_argv_cpus_flag_followed_by_value(
    _apptainer_argv_with_resource_caps,
):
    # Arrange
    argv = _apptainer_argv_with_resource_caps
    # Act
    value = argv[argv.index("--cpus") + 1]
    # Assert
    assert value == "2"


def test_apptainer_argv_pids_limit_flag_followed_by_value(
    _apptainer_argv_with_resource_caps,
):
    # Arrange
    argv = _apptainer_argv_with_resource_caps
    # Act
    value = argv[argv.index("--pids-limit") + 1]
    # Assert
    assert value == "256"


# ---------------------------------------------------------------------------
# ApptainerRunner — project mount + token forwarding.
# ---------------------------------------------------------------------------


@pytest.fixture
def _apptainer_argv(fake_runtime):
    from newb._container_runner import ApptainerRunner

    r = ApptainerRunner(
        skills_mount=fake_runtime, project_root=fake_runtime, which=_always_found
    )
    try:
        yield r._build_argv()
    finally:
        r.close()


def test_apptainer_argv_project_bind_container_path_is_work_project(_apptainer_argv):
    # Arrange
    argv = _apptainer_argv
    project_bind = next(a for a in argv if a.endswith(":/work/project"))
    _, _, container_part = project_bind.partition(":")
    # Act
    value = container_part
    # Assert
    assert value == "/work/project"


def test_apptainer_argv_project_bind_is_read_write(_apptainer_argv):
    # Arrange
    argv = _apptainer_argv
    project_bind = next(a for a in argv if a.endswith(":/work/project"))
    # Act
    has_ro = ":ro" in project_bind
    # Assert
    assert has_ro is False


def test_apptainer_argv_forwards_newb_api_key(_apptainer_argv):
    # Arrange
    argv = _apptainer_argv
    # Act
    forwarded = any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv)
    # Assert
    assert forwarded, argv


def test_apptainer_argv_does_not_forward_upstream_api_key(_apptainer_argv):
    # Arrange
    argv = _apptainer_argv
    # Act
    leaked = any(a.startswith("ANTHROPIC_API_KEY=") for a in argv)
    # Assert
    assert leaked is False, argv


# ---------------------------------------------------------------------------
# pip-cache mount option.
# ---------------------------------------------------------------------------


@pytest.fixture
def _pip_cache_argv(fake_runtime, tmp_path):
    from newb._container_runner import DockerRunner

    cache = tmp_path / "newb-pip"
    r = DockerRunner(
        skills_mount=fake_runtime,
        project_root=fake_runtime,
        pip_cache_dir=str(cache),
        which=_always_found,
    )
    try:
        yield {"argv": r._build_argv(), "cache": cache}
    finally:
        r.close()


def test_docker_argv_pip_cache_mkdirs_host_path(_pip_cache_argv):
    # Arrange
    info = _pip_cache_argv
    # Act
    exists = info["cache"].is_dir()
    # Assert
    assert exists, "runner should mkdir the cache dir"


def test_docker_argv_pip_cache_emits_bind_mount(_pip_cache_argv):
    # Arrange
    info = _pip_cache_argv
    # Act
    present = any(
        f"{info['cache']}:/home/newb/.cache/pip" == a for a in info["argv"]
    )
    # Assert
    assert present, info["argv"]


def test_docker_argv_no_pip_cache_when_unset(docker_argv):
    # Arrange
    argv = docker_argv
    # Act
    present = any("/home/newb/.cache/pip" in a for a in argv)
    # Assert
    assert present is False, argv
