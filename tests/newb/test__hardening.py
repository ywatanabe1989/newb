"""Tests for newb._hardening.HardeningOptions resolution.

Three-layer order: explicit kwargs > NEWB_HARDEN_* env vars > defaults.

Env-var-driven tests use the ``env_save_restore`` fixture from
``tests/conftest.py`` (yield-based snapshot/restore) instead of the
banned ``monkeypatch`` fixture.
"""

from __future__ import annotations

import pytest

from newb._hardening import (
    HardeningOptions,
    hardening_argv,
    hardening_summary,
)


# ---------------------------------------------------------------------------
# Default HardeningOptions — boundary-only: cap-drop, no-new-privs, bridge.
# Split per-field so the failure says exactly which default drifted.
# ---------------------------------------------------------------------------


@pytest.fixture
def _default_opts() -> HardeningOptions:
    return HardeningOptions()


def test_default_opts_cap_drop_all_is_true(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.cap_drop_all
    # Assert
    assert value is True


def test_default_opts_no_new_privileges_is_true(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.no_new_privileges
    # Assert
    assert value is True


def test_default_opts_no_network_is_false(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.no_network
    # Assert
    assert value is False


def test_default_opts_memory_is_none(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.memory
    # Assert
    assert value is None


def test_default_opts_cpus_is_none(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.cpus
    # Assert
    assert value is None


def test_default_opts_pids_limit_is_none(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.pids_limit
    # Assert
    assert value is None


def test_default_opts_tmpfs_noexec_is_false(_default_opts):
    # Arrange
    opts = _default_opts
    # Act
    value = opts.tmpfs_noexec
    # Assert
    assert value is False


# ---------------------------------------------------------------------------
# Default `hardening_argv()` — minimal, no resource caps. Split per flag.
# ---------------------------------------------------------------------------


@pytest.fixture
def _default_argv() -> list[str]:
    return hardening_argv()


def test_default_argv_has_cap_drop_all(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    present = "--cap-drop=ALL" in argv
    # Assert
    assert present


def test_default_argv_has_no_new_privileges(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    present = "--security-opt=no-new-privileges" in argv
    # Assert
    assert present


def test_default_argv_has_bridge_network(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    present = "--network=bridge" in argv
    # Assert
    assert present


def test_default_argv_has_no_memory_flag(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    matches = [a for a in argv if a.startswith("--memory=")]
    # Assert
    assert matches == []


def test_default_argv_has_no_cpus_flag(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    matches = [a for a in argv if a.startswith("--cpus=")]
    # Assert
    assert matches == []


def test_default_argv_has_no_pids_limit_flag(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    matches = [a for a in argv if a.startswith("--pids-limit=")]
    # Assert
    assert matches == []


def test_default_argv_has_no_tmpfs_flag(_default_argv):
    # Arrange
    argv = _default_argv
    # Act
    present = "--tmpfs" in argv
    # Assert
    assert present is False


# ---------------------------------------------------------------------------
# from_env() — resource cap parsing. Shared Arrange via fixture, per-field
# asserts.
# ---------------------------------------------------------------------------


@pytest.fixture
def _env_resource_caps(env_save_restore) -> tuple[HardeningOptions, list[str]]:
    env_save_restore("NEWB_HARDEN_MEMORY", "8g")
    env_save_restore("NEWB_HARDEN_MEMORY_SWAP", "8g")
    env_save_restore("NEWB_HARDEN_CPUS", "4")
    env_save_restore("NEWB_HARDEN_PIDS_LIMIT", "512")
    opts = HardeningOptions.from_env()
    return opts, hardening_argv(opts)


def test_from_env_picks_up_memory(_env_resource_caps):
    # Arrange
    opts, _ = _env_resource_caps
    # Act
    value = opts.memory
    # Assert
    assert value == "8g"


def test_from_env_picks_up_memory_swap(_env_resource_caps):
    # Arrange
    opts, _ = _env_resource_caps
    # Act
    value = opts.memory_swap
    # Assert
    assert value == "8g"


def test_from_env_picks_up_cpus(_env_resource_caps):
    # Arrange
    opts, _ = _env_resource_caps
    # Act
    value = opts.cpus
    # Assert
    assert value == "4"


def test_from_env_picks_up_pids_limit_as_int(_env_resource_caps):
    # Arrange
    opts, _ = _env_resource_caps
    # Act
    value = opts.pids_limit
    # Assert
    assert value == 512


def test_from_env_resource_caps_argv_has_memory_flag(_env_resource_caps):
    # Arrange
    _, argv = _env_resource_caps
    # Act
    present = "--memory=8g" in argv
    # Assert
    assert present


def test_from_env_resource_caps_argv_has_memory_swap_flag(_env_resource_caps):
    # Arrange
    _, argv = _env_resource_caps
    # Act
    present = "--memory-swap=8g" in argv
    # Assert
    assert present


def test_from_env_resource_caps_argv_has_cpus_flag(_env_resource_caps):
    # Arrange
    _, argv = _env_resource_caps
    # Act
    present = "--cpus=4" in argv
    # Assert
    assert present


def test_from_env_resource_caps_argv_has_pids_limit_flag(_env_resource_caps):
    # Arrange
    _, argv = _env_resource_caps
    # Act
    present = "--pids-limit=512" in argv
    # Assert
    assert present


def test_from_env_pids_limit_invalid_int_falls_back_to_none(env_save_restore):
    """Garbage in NEWB_HARDEN_PIDS_LIMIT shouldn't crash; just disable."""
    # Arrange
    env_save_restore("NEWB_HARDEN_PIDS_LIMIT", "not-a-number")
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.pids_limit is None


# ---------------------------------------------------------------------------
# NEWB_HARDEN_NO_NETWORK — truthy values. Parametrize to one intent per row,
# and split the 3-assertion body into three parametrized tests.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("truthy_value", ["1", "true", "True", "yes", "on"])
def test_from_env_no_network_truthy_value_sets_flag(truthy_value, env_save_restore):
    # Arrange
    env_save_restore("NEWB_HARDEN_NO_NETWORK", truthy_value)
    # Act
    opts = HardeningOptions.from_env()
    # Assert
    assert opts.no_network is True, f"value {truthy_value!r} should be truthy"


@pytest.mark.parametrize("truthy_value", ["1", "true", "True", "yes", "on"])
def test_from_env_no_network_truthy_value_argv_has_none_network(
    truthy_value, env_save_restore
):
    # Arrange
    env_save_restore("NEWB_HARDEN_NO_NETWORK", truthy_value)
    opts = HardeningOptions.from_env()
    # Act
    argv = hardening_argv(opts)
    # Assert
    assert "--network=none" in argv


@pytest.mark.parametrize("truthy_value", ["1", "true", "True", "yes", "on"])
def test_from_env_no_network_truthy_value_argv_drops_bridge(
    truthy_value, env_save_restore
):
    # Arrange
    env_save_restore("NEWB_HARDEN_NO_NETWORK", truthy_value)
    opts = HardeningOptions.from_env()
    # Act
    argv = hardening_argv(opts)
    # Assert
    assert "--network=bridge" not in argv


# ---------------------------------------------------------------------------
# cap_drop_all disable.
# ---------------------------------------------------------------------------


@pytest.fixture
def _cap_drop_disabled(env_save_restore) -> tuple[HardeningOptions, list[str]]:
    env_save_restore("NEWB_HARDEN_CAP_DROP_ALL", "0")
    opts = HardeningOptions.from_env()
    return opts, hardening_argv(opts)


def test_from_env_cap_drop_can_be_disabled_on_opts(_cap_drop_disabled):
    # Arrange
    opts, _ = _cap_drop_disabled
    # Act
    value = opts.cap_drop_all
    # Assert
    assert value is False


def test_from_env_cap_drop_disabled_argv_drops_flag(_cap_drop_disabled):
    # Arrange
    _, argv = _cap_drop_disabled
    # Act
    present = "--cap-drop=ALL" in argv
    # Assert
    assert present is False


def test_merged_with_kwargs_override_env(env_save_restore):
    """CLI flag layer: ``--harden-memory 16g`` clobbers env-supplied 8g."""
    # Arrange
    env_save_restore("NEWB_HARDEN_MEMORY", "8g")
    base = HardeningOptions.from_env()
    # Act
    cli = base.merged_with(memory="16g")
    # Assert
    assert cli.memory == "16g"


def test_merged_with_none_does_not_clobber_env_value(env_save_restore):
    """Absent CLI flag (None) must NOT erase env-supplied value."""
    # Arrange
    env_save_restore("NEWB_HARDEN_CPUS", "4")
    base = HardeningOptions.from_env()
    # Act
    cli = base.merged_with(cpus=None)
    # Assert
    assert cli.cpus == "4", "None override clobbered the env value"


def test_tmpfs_noexec_off_by_default():
    """pip and pytest occasionally write+exec wheels in /tmp."""
    # Arrange
    argv = hardening_argv()
    # Act
    has_noexec = any("noexec" in a for a in argv)
    # Assert
    assert has_noexec is False


# ---------------------------------------------------------------------------
# tmpfs_noexec opt-in. Three facets split.
# ---------------------------------------------------------------------------


@pytest.fixture
def _tmpfs_noexec_opted_in(env_save_restore) -> tuple[HardeningOptions, list[str]]:
    env_save_restore("NEWB_HARDEN_TMPFS_NOEXEC", "1")
    opts = HardeningOptions.from_env()
    return opts, hardening_argv(opts)


def test_tmpfs_noexec_opt_in_sets_flag(_tmpfs_noexec_opted_in):
    # Arrange
    opts, _ = _tmpfs_noexec_opted_in
    # Act
    value = opts.tmpfs_noexec
    # Assert
    assert value is True


def test_tmpfs_noexec_opt_in_argv_has_tmpfs_flag(_tmpfs_noexec_opted_in):
    # Arrange
    _, argv = _tmpfs_noexec_opted_in
    # Act
    present = "--tmpfs" in argv
    # Assert
    assert present


def test_tmpfs_noexec_opt_in_argv_value_contains_noexec(_tmpfs_noexec_opted_in):
    # Arrange
    _, argv = _tmpfs_noexec_opted_in
    tmpfs_idx = argv.index("--tmpfs")
    # Act
    value_token = argv[tmpfs_idx + 1]
    # Assert
    assert "noexec" in value_token


# ---------------------------------------------------------------------------
# Summary dict shape — pin each key separately so a missing one names itself.
# ---------------------------------------------------------------------------


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
def test_summary_shape_includes_key(key):
    """Summary feeds into the planned transparency-report header.

    Lock the dict shape so the renderer doesn't drift.
    """
    # Arrange
    s = hardening_summary()
    # Act
    present = key in s
    # Assert
    assert present, f"missing summary key: {key}"
