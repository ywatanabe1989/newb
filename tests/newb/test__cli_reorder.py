"""Tests for `_cli._reorder_argv` — natural option ordering.

Click's ``invoke_without_command=True`` group treats anything after the
SOURCE positional as a subcommand name, which breaks the natural CLI
ordering most users reach for first (`newb <path> --format markdown`).
The reorder hook moves the SOURCE positional to the end of argv so all
options precede it from Click's POV — but only when no real subcommand
is being invoked.
"""

from __future__ import annotations

from newb._cli import _reorder_argv


def test_options_after_source_get_reordered_before():
    """`newb <SRC> --format markdown` → `newb --format markdown <SRC>`."""
    assert _reorder_argv(["~/proj/newb", "--format", "markdown"]) == [
        "--format",
        "markdown",
        "~/proj/newb",
    ]


def test_flag_after_source_gets_reordered():
    assert _reorder_argv(["~/proj/newb", "--markdown"]) == [
        "--markdown",
        "~/proj/newb",
    ]


def test_options_already_before_source_left_alone():
    assert _reorder_argv(["--format", "markdown", "~/proj/newb"]) == [
        "--format",
        "markdown",
        "~/proj/newb",
    ]


def test_subcommand_invocation_left_alone():
    """Don't touch real subcommand invocations — Click handles those."""
    assert _reorder_argv(["templates", "list"]) == ["templates", "list"]
    assert _reorder_argv(["mcp", "start"]) == ["mcp", "start"]


def test_value_taking_option_does_not_eat_source():
    """`--runs 3 <SRC>` — `--runs` takes a value (3), not the SOURCE."""
    assert _reorder_argv(["--runs", "3", "~/proj/newb"]) == [
        "--runs",
        "3",
        "~/proj/newb",
    ]


def test_value_taking_option_after_source_gets_reordered():
    """`<SRC> --runs 3` → `--runs 3 <SRC>`."""
    assert _reorder_argv(["~/proj/newb", "--runs", "3"]) == [
        "--runs",
        "3",
        "~/proj/newb",
    ]


def test_no_args_returns_empty():
    assert _reorder_argv([]) == []


def test_just_source_returns_unchanged():
    assert _reorder_argv(["~/proj/newb"]) == ["~/proj/newb"]


def test_double_dash_separator_is_passthrough():
    """`--` means caller is doing explicit separation; don't reorder."""
    assert _reorder_argv(["~/proj/newb", "--", "--format", "json"]) == [
        "~/proj/newb",
        "--",
        "--format",
        "json",
    ]
