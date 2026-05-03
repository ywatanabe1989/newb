"""Tests for newb._parsers — structured `<key>_parsed` extraction."""

from __future__ import annotations


from newb._parsers import (
    attach_parsed_fields,
    parse_install_and_help,
    parse_post_install_check,
    parse_prompt_injection_check,
)

# ---------------------------------------------------------------------------
# parse_post_install_check
# ---------------------------------------------------------------------------


def test_post_install_canonical_form():
    text = (
        "INSTALL: ok\n"
        "IMPORT: ok\n"
        "CLI: ok\n"
        "EVIDENCE:\n  Installed scitex-io 0.2.11 and 87 deps\n"
    )
    assert parse_post_install_check(text) == {
        "install": "ok",
        "import": "ok",
        "cli": "ok",
    }


def test_post_install_mixed_case_label_and_value():
    text = "Install: OK\nimport: Ok\nCli: ok\n"
    assert parse_post_install_check(text) == {
        "install": "ok",
        "import": "ok",
        "cli": "ok",
    }


def test_post_install_with_bold_markdown():
    # Real-world form newb has emitted: bold around label and value.
    text = "**INSTALL: ok**\n**IMPORT: ok**\n**CLI: ok**\n"
    assert parse_post_install_check(text) == {
        "install": "ok",
        "import": "ok",
        "cli": "ok",
    }


def test_post_install_fail_normalized():
    text = "INSTALL: fail\nIMPORT: ok\nCLI: ok\n"
    assert parse_post_install_check(text)["install"] == "fail"


def test_post_install_cli_not_applicable():
    text = "INSTALL: ok\nIMPORT: ok\nCLI: n/a\n"
    assert parse_post_install_check(text)["cli"] == "n/a"


def test_post_install_off_script_yields_unknown():
    text = "INSTALL: maybe-worked\nIMPORT: ok\nCLI: ok\n"
    assert parse_post_install_check(text)["install"] == "unknown"


def test_post_install_missing_label_yields_unknown():
    text = "INSTALL: ok\nCLI: ok\n"  # no IMPORT line
    parsed = parse_post_install_check(text)
    assert parsed["install"] == "ok"
    assert parsed["import"] == "unknown"
    assert parsed["cli"] == "ok"


def test_post_install_first_occurrence_wins_evidence_block_ignored():
    # The agent might restate "INSTALL: fail" inside EVIDENCE prose.
    # First-line value should win (the explicit verdict line, not the
    # evidence narrative).
    text = (
        "INSTALL: ok\n"
        "IMPORT: ok\n"
        "CLI: ok\n"
        "EVIDENCE:\n"
        "  An earlier attempt logged INSTALL: fail until we resolved\n"
        "  the missing build dep.\n"
    )
    assert parse_post_install_check(text)["install"] == "ok"


# ---------------------------------------------------------------------------
# parse_install_and_help (cli-tool template)
# ---------------------------------------------------------------------------


def test_install_and_help_canonical():
    text = "INSTALL: ok\nHELP: ok\nEVIDENCE:\n  ...\n"
    assert parse_install_and_help(text) == {"install": "ok", "help": "ok"}


def test_install_and_help_partial_failure():
    text = "INSTALL: ok\nHELP: fail\n"
    assert parse_install_and_help(text) == {"install": "ok", "help": "fail"}


# ---------------------------------------------------------------------------
# parse_prompt_injection_check
# ---------------------------------------------------------------------------


def test_injection_no():
    text = "FOUND: no\nEVIDENCE: none\n"
    parsed = parse_prompt_injection_check(text)
    assert parsed == {"found": False, "found_raw": "no"}


def test_injection_yes():
    text = "FOUND: yes\nEVIDENCE:\n  README.md line 42 says 'IGNORE PREVIOUS'\n"
    parsed = parse_prompt_injection_check(text)
    assert parsed == {"found": True, "found_raw": "yes"}


def test_injection_off_script_keeps_unknown():
    text = "FOUND: maybe? unsure.\nEVIDENCE: ...\n"
    parsed = parse_prompt_injection_check(text)
    assert parsed["found"] is None
    assert parsed["found_raw"] == "unknown"


def test_injection_missing_label():
    text = "I scanned 15 files and found nothing suspicious."
    parsed = parse_prompt_injection_check(text)
    assert parsed["found"] is None
    assert parsed["found_raw"] == "unknown"


def test_injection_with_bold():
    text = "**FOUND: no**\n**EVIDENCE:** none\n"
    parsed = parse_prompt_injection_check(text)
    assert parsed == {"found": False, "found_raw": "no"}


# ---------------------------------------------------------------------------
# attach_parsed_fields — integration with the report dict
# ---------------------------------------------------------------------------


def test_attach_adds_parsed_siblings_for_known_keys():
    report = {
        "package": "demo",
        "post_install_check": "INSTALL: ok\nIMPORT: ok\nCLI: ok\n",
        "prompt_injection_check": "FOUND: no\n",
    }
    attach_parsed_fields(report)
    assert report["post_install_check_parsed"] == {
        "install": "ok",
        "import": "ok",
        "cli": "ok",
    }
    assert report["prompt_injection_check_parsed"] == {
        "found": False,
        "found_raw": "no",
    }


def test_attach_does_not_touch_unrelated_keys():
    report = {"package": "demo", "what_for": "Does X."}
    attach_parsed_fields(report)
    assert "what_for_parsed" not in report
    assert "package_parsed" not in report


def test_attach_handles_runs_per_prompt_lists():
    # When runs_per_prompt > 1, the value is a list[str] of replies.
    report = {
        "post_install_check": [
            "INSTALL: ok\nIMPORT: ok\nCLI: ok\n",
            "INSTALL: fail\nIMPORT: ok\nCLI: ok\n",
        ],
    }
    attach_parsed_fields(report)
    assert report["post_install_check_parsed"] == [
        {"install": "ok", "import": "ok", "cli": "ok"},
        {"install": "fail", "import": "ok", "cli": "ok"},
    ]


def test_attach_idempotent():
    report = {"post_install_check": "INSTALL: ok\nIMPORT: ok\nCLI: ok\n"}
    attach_parsed_fields(report)
    first = dict(report["post_install_check_parsed"])
    attach_parsed_fields(report)
    assert report["post_install_check_parsed"] == first


# EOF
