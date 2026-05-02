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
    argv = r._build_argv()

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
    argv = r._build_argv()
    assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    assert not any(a.startswith("ANTHROPIC_API_KEY=") for a in argv), argv
    # No credentials.json mount — the env-var path keeps newb usable in CI.
    assert not any(":/home/newb/.claude/.credentials.json" in a for a in argv), argv
    r.close()


def test_docker_argv_uses_versioned_image_by_default(fake_runtime):
    import newb
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    image_tag = argv[-1]
    assert image_tag.endswith(f":{newb.__version__}"), image_tag
    r.close()


def test_oauth_token_passes_through_opaquely(monkeypatch, fake_runtime):
    """OAuth tokens (sk-ant-oat*) pass through verbatim. Host runner
    does not inspect token shape — that's the in-container runner.py."""
    from newb._container_runner import DockerRunner

    monkeypatch.setenv("NEWB_ANTHROPIC_API_KEY", "sk-ant-oat01-TEST")

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
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


def test_docker_argv_includes_default_hardening(fake_runtime):
    """Default hardening: cap-drop=ALL, no-new-privileges, network=bridge.
    Resource caps stay off so the agent can exercise the package."""
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert "--network=bridge" in argv
    # No resource caps by default
    assert not any(a.startswith("--memory=") for a in argv), argv
    assert not any(a.startswith("--cpus=") for a in argv), argv
    assert not any(a.startswith("--pids-limit=") for a in argv), argv
    r.close()


def test_docker_argv_resource_caps_via_env(monkeypatch, fake_runtime):
    """NEWB_HARDEN_* env vars enable resource caps."""
    from newb._container_runner import DockerRunner

    monkeypatch.setenv("NEWB_HARDEN_MEMORY", "4g")
    monkeypatch.setenv("NEWB_HARDEN_CPUS", "2")
    monkeypatch.setenv("NEWB_HARDEN_PIDS_LIMIT", "256")

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    assert "--memory=4g" in argv
    assert "--cpus=2" in argv
    assert "--pids-limit=256" in argv
    r.close()


def test_docker_argv_no_network_via_env(monkeypatch, fake_runtime):
    """NEWB_HARDEN_NO_NETWORK=1 swaps bridge for none."""
    from newb._container_runner import DockerRunner

    monkeypatch.setenv("NEWB_HARDEN_NO_NETWORK", "1")
    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    assert "--network=none" in argv
    assert "--network=bridge" not in argv
    r.close()


def test_podman_argv_swaps_only_the_binary(fake_runtime):
    """PodmanRunner inherits everything from DockerRunner; only the
    leading ``docker`` token becomes ``podman``."""
    from newb._container_runner import PodmanRunner

    podman = PodmanRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = podman._build_argv()

    assert argv[0] == "podman"
    # Same flag shape as docker — same hardening + same env-var forwarding.
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert "--network=bridge" in argv
    assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv)
    podman.close()


def test_apptainer_argv_picks_up_resource_caps_from_env(monkeypatch, fake_runtime):
    """ApptainerRunner forwards memory/cpus/pids-limit from
    NEWB_HARDEN_* env vars (best-effort parity with docker; not all
    flags map cleanly — see apptainer_hardening_argv docstring)."""
    from newb._container_runner import ApptainerRunner

    monkeypatch.setenv("NEWB_HARDEN_MEMORY", "4g")
    monkeypatch.setenv("NEWB_HARDEN_CPUS", "2")
    monkeypatch.setenv("NEWB_HARDEN_PIDS_LIMIT", "256")

    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()

    # Apptainer takes flag value pairs, not docker-style --flag=value
    assert "--memory" in argv
    assert argv[argv.index("--memory") + 1] == "4g"
    assert "--cpus" in argv
    assert argv[argv.index("--cpus") + 1] == "2"
    assert "--pids-limit" in argv
    assert argv[argv.index("--pids-limit") + 1] == "256"
    r.close()


def test_apptainer_argv_mounts_project_and_forwards_token(fake_runtime):
    """ApptainerRunner mirrors DockerRunner: project bind-mount
    read-write, token forwarded as NEWB_ANTHROPIC_API_KEY env."""
    from newb._container_runner import ApptainerRunner

    r = ApptainerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    project_bind = next(a for a in argv if a.endswith(":/work/project"))
    _, _, container_part = project_bind.partition(":")
    assert container_part == "/work/project"
    assert ":ro" not in project_bind
    assert any(a == "NEWB_ANTHROPIC_API_KEY=sk-ant-api03-TEST" for a in argv), argv
    assert not any(a.startswith("ANTHROPIC_API_KEY=") for a in argv), argv
    r.close()


def test_docker_argv_mounts_pip_cache_when_configured(fake_runtime, tmp_path):
    """When NEWB_PIP_CACHE_DIR or pip_cache_dir is set, the docker argv
    mounts the host cache at /home/newb/.cache/pip (the runtime user's
    pip cache path)."""
    from newb._container_runner import DockerRunner

    cache = tmp_path / "newb-pip"
    r = DockerRunner(
        skills_mount=fake_runtime,
        project_root=fake_runtime,
        pip_cache_dir=str(cache),
    )
    argv = r._build_argv()
    assert cache.is_dir(), "runner should mkdir the cache dir"
    assert any(
        f"{cache}:/home/newb/.cache/pip" == a for a in argv
    ), argv
    r.close()


def test_docker_argv_no_pip_cache_when_unset(fake_runtime):
    from newb._container_runner import DockerRunner

    r = DockerRunner(skills_mount=fake_runtime, project_root=fake_runtime)
    argv = r._build_argv()
    assert not any("/home/newb/.cache/pip" in a for a in argv), argv
    r.close()
