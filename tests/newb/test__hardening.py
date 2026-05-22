"""Tests for newb._hardening.HardeningOptions resolution.

Three-layer order: explicit kwargs > NEWB_HARDEN_* env vars > defaults.

Env-var-driven tests use the ``env_save_restore`` fixture from
``tests/conftest.py`` (yield-based snapshot/restore) instead of the
banned ``monkeypatch`` fixture.
"""

from __future__ import annotations


from newb._hardening import (
    HardeningOptions,
    hardening_argv,
    hardening_summary,
)


def test_defaults_are_boundary_only():
    """Defaults: cap-drop, no-new-privs, bridge net. No resource caps —
    agent must run unconstrained inside the boundary so it can install
    + run + test the package."""
    opts = HardeningOptions()
    assert opts.cap_drop_all is True
    assert opts.no_new_privileges is True
    assert opts.no_network is False
    assert opts.memory is None
    assert opts.cpus is None
    assert opts.pids_limit is None
    assert opts.tmpfs_noexec is False


def test_default_argv_minimal():
    argv = hardening_argv()
    assert "--cap-drop=ALL" in argv
    assert "--security-opt=no-new-privileges" in argv
    assert "--network=bridge" in argv
    # Crucially: NO resource caps by default
    assert not any(a.startswith("--memory=") for a in argv), argv
    assert not any(a.startswith("--cpus=") for a in argv), argv
    assert not any(a.startswith("--pids-limit=") for a in argv), argv
    assert "--tmpfs" not in argv


def test_from_env_picks_up_resource_caps(env_save_restore):
    env_save_restore("NEWB_HARDEN_MEMORY", "8g")
    env_save_restore("NEWB_HARDEN_MEMORY_SWAP", "8g")
    env_save_restore("NEWB_HARDEN_CPUS", "4")
    env_save_restore("NEWB_HARDEN_PIDS_LIMIT", "512")

    opts = HardeningOptions.from_env()
    assert opts.memory == "8g"
    assert opts.memory_swap == "8g"
    assert opts.cpus == "4"
    assert opts.pids_limit == 512

    argv = hardening_argv(opts)
    assert "--memory=8g" in argv
    assert "--memory-swap=8g" in argv
    assert "--cpus=4" in argv
    assert "--pids-limit=512" in argv


def test_from_env_pids_limit_invalid_int_falls_back_to_none(env_save_restore):
    """Garbage in NEWB_HARDEN_PIDS_LIMIT shouldn't crash; just disable."""
    env_save_restore("NEWB_HARDEN_PIDS_LIMIT", "not-a-number")
    opts = HardeningOptions.from_env()
    assert opts.pids_limit is None


def test_from_env_no_network_truthy_values(env_save_restore):
    for v in ("1", "true", "True", "yes", "on"):
        env_save_restore("NEWB_HARDEN_NO_NETWORK", v)
        opts = HardeningOptions.from_env()
        assert opts.no_network is True, f"value {v!r} should be truthy"
        argv = hardening_argv(opts)
        assert "--network=none" in argv
        assert "--network=bridge" not in argv


def test_from_env_cap_drop_can_be_disabled(env_save_restore):
    env_save_restore("NEWB_HARDEN_CAP_DROP_ALL", "0")
    opts = HardeningOptions.from_env()
    assert opts.cap_drop_all is False
    argv = hardening_argv(opts)
    assert "--cap-drop=ALL" not in argv


def test_merged_with_kwargs_override_env(env_save_restore):
    """CLI flag layer: ``--harden-memory 16g`` clobbers env-supplied 8g."""
    env_save_restore("NEWB_HARDEN_MEMORY", "8g")
    base = HardeningOptions.from_env()
    cli = base.merged_with(memory="16g")
    assert cli.memory == "16g"


def test_merged_with_none_does_not_clobber(env_save_restore):
    """Absent CLI flag (None) must NOT erase env-supplied value."""
    env_save_restore("NEWB_HARDEN_CPUS", "4")
    base = HardeningOptions.from_env()
    cli = base.merged_with(cpus=None)
    assert cli.cpus == "4", "None override clobbered the env value"


def test_tmpfs_noexec_off_by_default():
    """pip and pytest occasionally write+exec wheels in /tmp."""
    argv = hardening_argv()
    assert not any("noexec" in a for a in argv)


def test_tmpfs_noexec_opt_in(env_save_restore):
    env_save_restore("NEWB_HARDEN_TMPFS_NOEXEC", "1")
    opts = HardeningOptions.from_env()
    assert opts.tmpfs_noexec is True
    argv = hardening_argv(opts)
    assert "--tmpfs" in argv
    tmpfs_idx = argv.index("--tmpfs")
    assert "noexec" in argv[tmpfs_idx + 1]


def test_summary_shape_for_transparency_report():
    """Summary feeds into the planned transparency-report header.

    Lock the dict shape so the renderer doesn't drift.
    """
    s = hardening_summary()
    for key in (
        "cap-drop",
        "no-new-privs",
        "network",
        "memory-limit",
        "cpus-limit",
        "pids-limit",
        "tmpfs-noexec",
        "agent-resources" if False else "memory-swap",  # presence-only
    ):
        assert key in s, f"missing summary key: {key}"
