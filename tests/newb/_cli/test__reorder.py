"""Tests for `_cli._reorder_argv` — natural option ordering.

Click's ``invoke_without_command=True`` group treats anything after the
SOURCE positional as a subcommand name, which breaks the natural CLI
ordering most users reach for first (`newb <path> --format markdown`).
The reorder hook moves the SOURCE positional to the end of argv so all
options precede it from Click's POV — but only when no real subcommand
is being invoked.
"""

from __future__ import annotations

import pytest

from newb._cli._reorder import _reorder_argv


def test_options_after_source_get_reordered_before():
    # Arrange
    argv = ["~/proj/newb", "--format", "markdown"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["--format", "markdown", "~/proj/newb"]


def test_flag_after_source_gets_reordered_before():
    # Arrange
    argv = ["~/proj/newb", "--markdown"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["--markdown", "~/proj/newb"]


def test_options_already_before_source_left_alone():
    # Arrange
    argv = ["--format", "markdown", "~/proj/newb"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["--format", "markdown", "~/proj/newb"]


@pytest.mark.parametrize("argv", [["templates", "list"], ["mcp", "start"]])
def test_subcommand_invocation_left_alone(argv):
    # Arrange
    expected = list(argv)
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == expected


def test_value_taking_option_before_source_does_not_eat_source():
    # Arrange
    argv = ["--runs", "3", "~/proj/newb"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["--runs", "3", "~/proj/newb"]


def test_value_taking_option_after_source_gets_reordered():
    # Arrange
    argv = ["~/proj/newb", "--runs", "3"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["--runs", "3", "~/proj/newb"]


def test_no_args_returns_empty():
    # Arrange
    # Act
    reordered = _reorder_argv([])
    # Assert
    assert reordered == []


def test_just_source_returns_unchanged():
    # Arrange
    argv = ["~/proj/newb"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["~/proj/newb"]


def test_double_dash_separator_is_passthrough():
    # Arrange
    argv = ["~/proj/newb", "--", "--format", "json"]
    # Act
    reordered = _reorder_argv(argv)
    # Assert
    assert reordered == ["~/proj/newb", "--", "--format", "json"]
