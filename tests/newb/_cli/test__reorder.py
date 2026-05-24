"""Tests for `_cli._reorder_argv` — natural option ordering.

Click's ``invoke_without_command=True`` group treats anything after the
SOURCE positional as a subcommand name, which breaks the natural CLI
ordering most users reach for first (`newb <path> --format markdown`).
The reorder hook moves the SOURCE positional to the end of argv so all
options precede it from Click's POV — but only when no real subcommand
is being invoked.
"""

from __future__ import annotations

from newb._cli._reorder import _reorder_argv


def test_options_after_source_get_reordered_before():
    """`newb <SRC> --format markdown` → `newb --format markdown <SRC>`."""
    # Arrange
    argv = ["~/proj/newb", "--format", "markdown"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["--format", "markdown", "~/proj/newb"]


def test_flag_after_source_gets_reordered_before():
    # Arrange
    argv = ["~/proj/newb", "--markdown"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["--markdown", "~/proj/newb"]


def test_options_already_before_source_left_alone():
    # Arrange
    argv = ["--format", "markdown", "~/proj/newb"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["--format", "markdown", "~/proj/newb"]


def test_templates_subcommand_invocation_left_alone():
    """Don't touch real subcommand invocations — Click handles those."""
    # Arrange
    argv = ["templates", "list"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["templates", "list"]


def test_mcp_subcommand_invocation_left_alone():
    # Arrange
    argv = ["mcp", "start"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["mcp", "start"]


def test_value_taking_option_does_not_eat_source():
    """`--runs 3 <SRC>` — `--runs` takes a value (3), not the SOURCE."""
    # Arrange
    argv = ["--runs", "3", "~/proj/newb"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["--runs", "3", "~/proj/newb"]


def test_value_taking_option_after_source_gets_reordered_before():
    """`<SRC> --runs 3` → `--runs 3 <SRC>`."""
    # Arrange
    argv = ["~/proj/newb", "--runs", "3"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["--runs", "3", "~/proj/newb"]


def test_no_args_returns_empty_list():
    # Arrange
    argv: list[str] = []
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == []


def test_just_source_returns_unchanged_argv():
    # Arrange
    argv = ["~/proj/newb"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["~/proj/newb"]


def test_double_dash_separator_is_passthrough():
    """`--` means caller is doing explicit separation; don't reorder."""
    # Arrange
    argv = ["~/proj/newb", "--", "--format", "json"]
    # Act
    out = _reorder_argv(argv)
    # Assert
    assert out == ["~/proj/newb", "--", "--format", "json"]
