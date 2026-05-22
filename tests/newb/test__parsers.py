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
    # Arrange
    text = (
        "INSTALL: ok\n"
        "IMPORT: ok\n"
        "CLI: ok\n"
        "EVIDENCE:\n  Installed scitex-io 0.2.11 and 87 deps\n"
    )
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed == {"install": "ok", "import": "ok", "cli": "ok"}


def test_post_install_mixed_case_label_and_value():
    # Arrange
    text = "Install: OK\nimport: Ok\nCli: ok\n"
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed == {"install": "ok", "import": "ok", "cli": "ok"}


def test_post_install_with_bold_markdown():
    # Arrange
    text = "**INSTALL: ok**\n**IMPORT: ok**\n**CLI: ok**\n"
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed == {"install": "ok", "import": "ok", "cli": "ok"}


def test_post_install_fail_normalized():
    # Arrange
    text = "INSTALL: fail\nIMPORT: ok\nCLI: ok\n"
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed["install"] == "fail"


def test_post_install_cli_not_applicable():
    # Arrange
    text = "INSTALL: ok\nIMPORT: ok\nCLI: n/a\n"
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed["cli"] == "n/a"


def test_post_install_off_script_yields_unknown():
    # Arrange
    text = "INSTALL: maybe-worked\nIMPORT: ok\nCLI: ok\n"
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed["install"] == "unknown"


def test_post_install_missing_label_yields_unknown_for_that_label():
    # Arrange
    text = "INSTALL: ok\nCLI: ok\n"  # no IMPORT line
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed["import"] == "unknown"


def test_post_install_missing_label_keeps_present_labels():
    # Arrange
    text = "INSTALL: ok\nCLI: ok\n"  # no IMPORT line
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed["install"] == "ok" and parsed["cli"] == "ok"


def test_post_install_verdict_line_wins_over_evidence_prose():
    # Arrange
    text = (
        "INSTALL: ok\n"
        "IMPORT: ok\n"
        "CLI: ok\n"
        "EVIDENCE:\n"
        "  An earlier attempt logged INSTALL: fail until we resolved\n"
        "  the missing build dep.\n"
    )
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed["install"] == "ok"


# ---------------------------------------------------------------------------
# parse_install_and_help (cli-tool template)
# ---------------------------------------------------------------------------


def test_install_and_help_canonical():
    # Arrange
    text = "INSTALL: ok\nHELP: ok\nEVIDENCE:\n  ...\n"
    # Act
    parsed = parse_install_and_help(text)
    # Assert
    assert parsed == {"install": "ok", "help": "ok"}


def test_install_and_help_partial_failure():
    # Arrange
    text = "INSTALL: ok\nHELP: fail\n"
    # Act
    parsed = parse_install_and_help(text)
    # Assert
    assert parsed == {"install": "ok", "help": "fail"}


# ---------------------------------------------------------------------------
# parse_prompt_injection_check
# ---------------------------------------------------------------------------


def test_injection_found_no_parses_to_false():
    # Arrange
    text = "FOUND: no\nEVIDENCE: none\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed == {"found": False, "found_raw": "no"}


def test_injection_found_yes_parses_to_true():
    # Arrange
    text = "FOUND: yes\nEVIDENCE:\n  README.md line 42 says 'IGNORE PREVIOUS'\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed == {"found": True, "found_raw": "yes"}


def test_injection_off_script_keeps_found_none():
    # Arrange
    text = "FOUND: maybe? unsure.\nEVIDENCE: ...\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed["found"] is None


def test_injection_off_script_raw_is_unknown():
    # Arrange
    text = "FOUND: maybe? unsure.\nEVIDENCE: ...\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed["found_raw"] == "unknown"


def test_injection_missing_label_keeps_found_none():
    # Arrange
    text = "I scanned 15 files and found nothing suspicious."
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed["found"] is None


def test_injection_with_bold():
    # Arrange
    text = "**FOUND: no**\n**EVIDENCE:** none\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed == {"found": False, "found_raw": "no"}


# ---------------------------------------------------------------------------
# attach_parsed_fields — integration with the report dict
# ---------------------------------------------------------------------------


def test_attach_adds_post_install_parsed_sibling():
    # Arrange
    report = {
        "package": "demo",
        "post_install_check": "INSTALL: ok\nIMPORT: ok\nCLI: ok\n",
    }
    # Act
    attach_parsed_fields(report)
    # Assert
    assert report["post_install_check_parsed"] == {
        "install": "ok",
        "import": "ok",
        "cli": "ok",
    }


def test_attach_adds_injection_parsed_sibling():
    # Arrange
    report = {"prompt_injection_check": "FOUND: no\n"}
    # Act
    attach_parsed_fields(report)
    # Assert
    assert report["prompt_injection_check_parsed"] == {
        "found": False,
        "found_raw": "no",
    }


def test_attach_does_not_touch_unrelated_keys():
    # Arrange
    report = {"package": "demo", "what_for": "Does X."}
    # Act
    attach_parsed_fields(report)
    # Assert
    assert "what_for_parsed" not in report and "package_parsed" not in report


def test_attach_handles_runs_per_prompt_lists():
    # Arrange
    report = {
        "post_install_check": [
            "INSTALL: ok\nIMPORT: ok\nCLI: ok\n",
            "INSTALL: fail\nIMPORT: ok\nCLI: ok\n",
        ],
    }
    # Act
    attach_parsed_fields(report)
    # Assert
    assert report["post_install_check_parsed"] == [
        {"install": "ok", "import": "ok", "cli": "ok"},
        {"install": "fail", "import": "ok", "cli": "ok"},
    ]


def test_attach_is_idempotent():
    # Arrange
    report = {"post_install_check": "INSTALL: ok\nIMPORT: ok\nCLI: ok\n"}
    attach_parsed_fields(report)
    first = dict(report["post_install_check_parsed"])
    # Act
    attach_parsed_fields(report)
    # Assert
    assert report["post_install_check_parsed"] == first


# ---------------------------------------------------------------------------
# ```newb-json block precedence (Tool-Use-shaped emission)
# ---------------------------------------------------------------------------


def test_newb_json_block_overrides_regex_post_install():
    # Arrange
    text = (
        "INSTALL: fail\nIMPORT: fail\nCLI: fail\n"
        "EVIDENCE: prose got the wrong answer\n\n"
        "```newb-json\n"
        '{"install": "ok", "import": "ok", "cli": "ok"}\n'
        "```\n"
    )
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed == {"install": "ok", "import": "ok", "cli": "ok"}


def test_newb_json_block_partial_keys_only_override_present():
    # Arrange
    text = 'INSTALL: ok\nIMPORT: fail\nCLI: ok\n\n```newb-json\n{"import": "ok"}\n```\n'
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed == {"install": "ok", "import": "ok", "cli": "ok"}


def test_newb_json_block_malformed_falls_back_to_regex():
    # Arrange
    text = "INSTALL: ok\nIMPORT: ok\nCLI: ok\n\n```newb-json\n{not valid json}\n```\n"
    # Act
    parsed = parse_post_install_check(text)
    # Assert
    assert parsed == {"install": "ok", "import": "ok", "cli": "ok"}


def test_newb_json_block_overrides_injection_found_bool():
    # Arrange
    text = (
        'FOUND: yes\nEVIDENCE: prose said yes\n\n```newb-json\n{"found": false}\n```\n'
    )
    # Act
    out = parse_prompt_injection_check(text)
    # Assert
    assert out["found"] is False


def test_newb_json_block_overrides_injection_found_raw():
    # Arrange
    text = (
        'FOUND: yes\nEVIDENCE: prose said yes\n\n```newb-json\n{"found": false}\n```\n'
    )
    # Act
    out = parse_prompt_injection_check(text)
    # Assert
    assert out["found_raw"] == "no"


def test_newb_json_block_install_and_help_override():
    # Arrange
    text = (
        "INSTALL: fail\nHELP: fail\n\n"
        '```newb-json\n{"install": "ok", "help": "ok"}\n```\n'
    )
    # Act
    parsed = parse_install_and_help(text)
    # Assert
    assert parsed == {"install": "ok", "help": "ok"}
