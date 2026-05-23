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
    out = parse_post_install_check(text)
    # Assert
    assert out == {"install": "ok", "import": "ok", "cli": "ok"}


def test_post_install_mixed_case_label_and_value():
    # Arrange
    text = "Install: OK\nimport: Ok\nCli: ok\n"
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out == {"install": "ok", "import": "ok", "cli": "ok"}


def test_post_install_with_bold_markdown():
    # Arrange
    # Real-world form newb has emitted: bold around label and value.
    text = "**INSTALL: ok**\n**IMPORT: ok**\n**CLI: ok**\n"
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out == {"install": "ok", "import": "ok", "cli": "ok"}


def test_post_install_fail_normalized():
    # Arrange
    text = "INSTALL: fail\nIMPORT: ok\nCLI: ok\n"
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out["install"] == "fail"


def test_post_install_cli_not_applicable():
    # Arrange
    text = "INSTALL: ok\nIMPORT: ok\nCLI: n/a\n"
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out["cli"] == "n/a"


def test_post_install_off_script_yields_unknown():
    # Arrange
    text = "INSTALL: maybe-worked\nIMPORT: ok\nCLI: ok\n"
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out["install"] == "unknown"


# ---------------------------------------------------------------------------
# Missing-label case: shared Arrange, one assert per dimension.
# ---------------------------------------------------------------------------


def _parse_missing_import_label() -> dict:
    """Arrange-block helper: INSTALL+CLI present, IMPORT label absent."""
    text = "INSTALL: ok\nCLI: ok\n"  # no IMPORT line
    return parse_post_install_check(text)


def test_post_install_missing_label_install_still_ok():
    # Arrange
    parsed = _parse_missing_import_label()
    # Act
    value = parsed["install"]
    # Assert
    assert value == "ok"


def test_post_install_missing_label_import_yields_unknown():
    # Arrange
    parsed = _parse_missing_import_label()
    # Act
    value = parsed["import"]
    # Assert
    assert value == "unknown"


def test_post_install_missing_label_cli_still_ok():
    # Arrange
    parsed = _parse_missing_import_label()
    # Act
    value = parsed["cli"]
    # Assert
    assert value == "ok"


def test_post_install_first_occurrence_wins_evidence_block_ignored():
    # Arrange
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
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out["install"] == "ok"


# ---------------------------------------------------------------------------
# parse_install_and_help (cli-tool template)
# ---------------------------------------------------------------------------


def test_install_and_help_canonical():
    # Arrange
    text = "INSTALL: ok\nHELP: ok\nEVIDENCE:\n  ...\n"
    # Act
    out = parse_install_and_help(text)
    # Assert
    assert out == {"install": "ok", "help": "ok"}


def test_install_and_help_partial_failure():
    # Arrange
    text = "INSTALL: ok\nHELP: fail\n"
    # Act
    out = parse_install_and_help(text)
    # Assert
    assert out == {"install": "ok", "help": "fail"}


# ---------------------------------------------------------------------------
# parse_prompt_injection_check
# ---------------------------------------------------------------------------


def test_injection_check_parses_found_no_as_false():
    # Arrange
    text = "FOUND: no\nEVIDENCE: none\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed == {"found": False, "found_raw": "no"}


def test_injection_check_parses_found_yes_as_true():
    # Arrange
    text = "FOUND: yes\nEVIDENCE:\n  README.md line 42 says 'IGNORE PREVIOUS'\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed == {"found": True, "found_raw": "yes"}


# ---------------------------------------------------------------------------
# Off-script "found" — shared Arrange, two facets split.
# ---------------------------------------------------------------------------


def _parse_off_script_found() -> dict:
    text = "FOUND: maybe? unsure.\nEVIDENCE: ...\n"
    return parse_prompt_injection_check(text)


def test_injection_off_script_found_is_none():
    # Arrange
    parsed = _parse_off_script_found()
    # Act
    value = parsed["found"]
    # Assert
    assert value is None


def test_injection_off_script_found_raw_is_unknown():
    # Arrange
    parsed = _parse_off_script_found()
    # Act
    value = parsed["found_raw"]
    # Assert
    assert value == "unknown"


def _parse_missing_injection_label() -> dict:
    text = "I scanned 15 files and found nothing suspicious."
    return parse_prompt_injection_check(text)


def test_injection_missing_label_found_is_none():
    # Arrange
    parsed = _parse_missing_injection_label()
    # Act
    value = parsed["found"]
    # Assert
    assert value is None


def test_injection_missing_label_found_raw_is_unknown():
    # Arrange
    parsed = _parse_missing_injection_label()
    # Act
    value = parsed["found_raw"]
    # Assert
    assert value == "unknown"


def test_injection_with_bold_markdown():
    # Arrange
    text = "**FOUND: no**\n**EVIDENCE:** none\n"
    # Act
    parsed = parse_prompt_injection_check(text)
    # Assert
    assert parsed == {"found": False, "found_raw": "no"}


# ---------------------------------------------------------------------------
# attach_parsed_fields — integration with the report dict
# ---------------------------------------------------------------------------


def _attach_known_keys_report() -> dict:
    report = {
        "package": "demo",
        "post_install_check": "INSTALL: ok\nIMPORT: ok\nCLI: ok\n",
        "prompt_injection_check": "FOUND: no\n",
    }
    attach_parsed_fields(report)
    return report


def test_attach_adds_post_install_parsed_sibling():
    # Arrange
    report = _attach_known_keys_report()
    # Act
    value = report.get("post_install_check_parsed")
    # Assert
    assert value == {"install": "ok", "import": "ok", "cli": "ok"}


def test_attach_adds_prompt_injection_parsed_sibling():
    # Arrange
    report = _attach_known_keys_report()
    # Act
    value = report.get("prompt_injection_check_parsed")
    # Assert
    assert value == {"found": False, "found_raw": "no"}


def _attach_unrelated_keys_report() -> dict:
    report = {"package": "demo", "what_for": "Does X."}
    attach_parsed_fields(report)
    return report


def test_attach_does_not_create_what_for_parsed():
    # Arrange
    report = _attach_unrelated_keys_report()
    # Act
    present = "what_for_parsed" in report
    # Assert
    assert present is False


def test_attach_does_not_create_package_parsed():
    # Arrange
    report = _attach_unrelated_keys_report()
    # Act
    present = "package_parsed" in report
    # Assert
    assert present is False


def test_attach_handles_runs_per_prompt_lists():
    # Arrange
    # When runs_per_prompt > 1, the value is a list[str] of replies.
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


def test_attach_parsed_fields_is_idempotent_on_re_call():
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
    out = parse_post_install_check(text)
    # Assert
    assert out == {"install": "ok", "import": "ok", "cli": "ok"}


def test_newb_json_block_partial_keys_only_override_present_keys():
    # Arrange
    text = 'INSTALL: ok\nIMPORT: fail\nCLI: ok\n\n```newb-json\n{"import": "ok"}\n```\n'
    # Act
    # install/cli stay from regex; import overridden by JSON.
    out = parse_post_install_check(text)
    # Assert
    assert out == {"install": "ok", "import": "ok", "cli": "ok"}


def test_newb_json_block_malformed_falls_back_to_regex():
    # Arrange
    text = "INSTALL: ok\nIMPORT: ok\nCLI: ok\n\n```newb-json\n{not valid json}\n```\n"
    # Act
    out = parse_post_install_check(text)
    # Assert
    assert out == {"install": "ok", "import": "ok", "cli": "ok"}


def _parse_injection_with_json_override() -> dict:
    text = (
        'FOUND: yes\nEVIDENCE: prose said yes\n\n```newb-json\n{"found": false}\n```\n'
    )
    return parse_prompt_injection_check(text)


def test_newb_json_block_overrides_injection_check_found_bool():
    # Arrange
    out = _parse_injection_with_json_override()
    # Act
    value = out["found"]
    # Assert
    assert value is False


def test_newb_json_block_overrides_injection_check_found_raw():
    # Arrange
    out = _parse_injection_with_json_override()
    # Act
    value = out["found_raw"]
    # Assert
    assert value == "no"


def test_newb_json_block_install_and_help_override():
    # Arrange
    text = (
        "INSTALL: fail\nHELP: fail\n\n"
        '```newb-json\n{"install": "ok", "help": "ok"}\n```\n'
    )
    # Act
    out = parse_install_and_help(text)
    # Assert
    assert out == {"install": "ok", "help": "ok"}


# EOF
