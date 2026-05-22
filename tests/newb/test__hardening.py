"""Tests for newb._hardening.HardeningOptions resolution.

Three-layer order: explicit kwargs > NEWB_HARDEN_* env vars > defaults.
"""

from __future__ import annotations

import pytest

from newb._hardening import (
    HardeningOptions,
    hardening_argv,
    hardening_summary,
)


def test_defaults_drop_all_caps():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.cap_drop_all is True


def test_defaults_set_no_new_privileges():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.no_new_privileges is True


def test_defaults_leave_network_on():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.no_network is False


def test_defaults_set_no_memory_cap():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.memory is None


def test_defaults_set_no_cpu_cap():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.cpus is None


def test_defaults_set_no_pids_cap():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.pids_limit is None


def test_defaults_leave_tmpfs_noexec_off():
    # Arrange
    # Act
    opts = HardeningOptions()
    # Assert
    assert opts.tmpfs_noexec is False


def test_default_argv_includes_cap_drop():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert "--cap-drop=ALL" in argv


def test_default_argv_includes_no_new_privileges():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert "--security-opt=no-new-privileges" in argv


def test_default_argv_uses_bridge_network():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert "--network=bridge" in argv


def test_default_argv_omits_memory_cap():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert not any(a.startswith("--memory=") for a in argv), argv


def test_default_argv_omits_cpu_cap():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert not any(a.startswith("--cpus=") for a in argv), argv


def test_default_argv_omits_pids_cap():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert not any(a.startswith("--pids-limit=") for a in argv), argv


def test_default_argv_omits_tmpfs():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert "--tmpfs" not in argv


def test_from_env_reads_memory_cap(env_set):
    # Arrange
    env_set("NEWB_HARDEN_MEMORY", "8g")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.memory == "8g"


def test_from_env_reads_memory_swap(env_set):
    # Arrange
    env_set("NEWB_HARDEN_MEMORY_SWAP", "8g")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.memory_swap == "8g"


def test_from_env_reads_cpu_cap(env_set):
    # Arrange
    env_set("NEWB_HARDEN_CPUS", "4")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.cpus == "4"


def test_from_env_reads_pids_cap(env_set):
    # Arrange
    env_set("NEWB_HARDEN_PIDS_LIMIT", "512")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.pids_limit == 512


def test_from_env_renders_memory_argv(env_set):
    # Arrange
    env_set("NEWB_HARDEN_MEMORY", "8g")
    # Act
    argv = hardening_argv(HardeningOptions.from_env())
    # Assert
    assert "--memory=8g" in argv


def test_from_env_renders_memory_swap_argv(env_set):
    # Arrange
    env_set("NEWB_HARDEN_MEMORY_SWAP", "8g")
    # Act
    argv = hardening_argv(HardeningOptions.from_env())
    # Assert
    assert "--memory-swap=8g" in argv


def test_from_env_renders_cpus_argv(env_set):
    # Arrange
    env_set("NEWB_HARDEN_CPUS", "4")
    # Act
    argv = hardening_argv(HardeningOptions.from_env())
    # Assert
    assert "--cpus=4" in argv


def test_from_env_renders_pids_argv(env_set):
    # Arrange
    env_set("NEWB_HARDEN_PIDS_LIMIT", "512")
    # Act
    argv = hardening_argv(HardeningOptions.from_env())
    # Assert
    assert "--pids-limit=512" in argv


def test_from_env_pids_limit_invalid_int_falls_back_to_none(env_set):
    # Arrange
    env_set("NEWB_HARDEN_PIDS_LIMIT", "not-a-number")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.pids_limit is None


@pytest.mark.parametrize("truthy", ["1", "true", "True", "yes", "on"])
def test_from_env_no_network_truthy_sets_flag(env_set, truthy):
    # Arrange
    env_set("NEWB_HARDEN_NO_NETWORK", truthy)
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.no_network is True


@pytest.mark.parametrize("truthy", ["1", "true", "True", "yes", "on"])
def test_from_env_no_network_truthy_renders_network_none(env_set, truthy):
    # Arrange
    env_set("NEWB_HARDEN_NO_NETWORK", truthy)
    # Act
    argv = hardening_argv(HardeningOptions.from_env())
    # Assert
    assert "--network=none" in argv


def test_from_env_cap_drop_can_be_disabled_on_opts(env_set):
    # Arrange
    env_set("NEWB_HARDEN_CAP_DROP_ALL", "0")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.cap_drop_all is False


def test_from_env_cap_drop_disabled_drops_argv_flag(env_set):
    # Arrange
    env_set("NEWB_HARDEN_CAP_DROP_ALL", "0")
    # Act
    argv = hardening_argv(HardeningOptions.from_env())
    # Assert
    assert "--cap-drop=ALL" not in argv


def test_merged_with_kwargs_override_env(env_set):
    # Arrange
    env_set("NEWB_HARDEN_MEMORY", "8g")
    base = HardeningOptions.from_env()
    # Act
    cli = base.merged_with(memory="16g")
    # Assert
    assert cli.memory == "16g"


def test_merged_with_none_does_not_clobber(env_set):
    # Arrange
    env_set("NEWB_HARDEN_CPUS", "4")
    base = HardeningOptions.from_env()
    # Act
    cli = base.merged_with(cpus=None)
    # Assert
    assert cli.cpus == "4"


def test_tmpfs_noexec_off_by_default():
    # Arrange
    # Act
    argv = hardening_argv()
    # Assert
    assert not any("noexec" in a for a in argv)


def test_tmpfs_noexec_opt_in_sets_flag(env_set):
    # Arrange
    env_set("NEWB_HARDEN_TMPFS_NOEXEC", "1")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.tmpfs_noexec is True


def test_tmpfs_noexec_opt_in_renders_noexec_argv(env_set):
    # Arrange
    env_set("NEWB_HARDEN_TMPFS_NOEXEC", "1")
    argv = hardening_argv(HardeningOptions.from_env())
    # Act
    tmpfs_idx = argv.index("--tmpfs")
    # Assert
    assert "noexec" in argv[tmpfs_idx + 1]


@pytest.mark.parametrize(
    "key",
    [
        "cap-drop",
        "no-new-privs",
        "network",
        "memory-limit",
        "cpus-limit",
        "pids-limit",
        "tmpfs-noexec",
        "memory-swap",
    ],
)
def test_summary_includes_transparency_key(key):
    # Arrange
    # Act
    s = hardening_summary()
    # Assert
    assert key in s, f"missing summary key: {key}"
