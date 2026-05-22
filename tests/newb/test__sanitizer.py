"""Tests for newb._sanitizer.

Migrated from the third-party audit drop's
test_security_0_11.py::TestSanitizer block, with the tuple-walk
regression added for the bug found during QA review.
"""

from __future__ import annotations

import pytest

from newb._sanitizer import (
    KEY_PROTECTION_SYSTEM_PROMPT,
    REDACTED_TOKEN,
    sanitize,
    sanitize_report,
)

_API_KEY = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_OAT_TOKEN = "sk-ant-oat01-BBBBBBBBBBBBBBBBBBBBBBBBBBBB"


def test_clean_text_is_not_flagged_as_leaked():
    # Arrange
    text = "Just a normal package description."
    # Act
    r = sanitize(text)
    # Assert
    assert not r.leaked


def test_clean_text_passes_through_unchanged():
    # Arrange
    text = "Just a normal package description."
    # Act
    r = sanitize(text)
    # Assert
    assert r.text == text


def test_plaintext_api_key_flagged_as_leaked():
    # Arrange
    text = f"The key is {_API_KEY} done."
    # Act
    r = sanitize(text)
    # Assert
    assert r.leaked


def test_plaintext_api_key_redacted_in_text():
    # Arrange
    text = f"The key is {_API_KEY} done."
    # Act
    r = sanitize(text)
    # Assert
    assert "sk-ant-api03" not in r.text


def test_plaintext_api_key_substitutes_redacted_token():
    # Arrange
    text = f"The key is {_API_KEY} done."
    # Act
    r = sanitize(text)
    # Assert
    assert REDACTED_TOKEN in r.text


def test_oat_token_flagged_as_leaked():
    # Arrange
    text = f"Token: {_OAT_TOKEN}."
    # Act
    r = sanitize(text)
    # Assert
    assert "anthropic_api_key_plaintext" in r.matches


def test_short_placeholder_not_matched():
    # Arrange
    text = "Set NEWB_ANTHROPIC_API_KEY to sk-ant-api03-..."
    # Act
    r = sanitize(text)
    # Assert
    assert not r.leaked, f"placeholder should not match, got {r.matches}"


def test_base64_prefix_redacted():
    # Arrange
    text = (
        "encoded: c2stYW50LWFwaTAzLUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB"
        "QUFBQUFBQUFBQUFBQUFB= end"
    )
    # Act
    r = sanitize(text)
    # Assert
    assert "anthropic_api_key_base64_prefix" in r.matches


def test_sanitize_report_redacts_secret_in_nested_list():
    # Arrange
    report = {
        "examples": ["fine", f"leaked: {_API_KEY[:-2]}CC"],
    }
    # Act
    clean, _ = sanitize_report(report)
    # Assert
    assert REDACTED_TOKEN in clean["examples"][1]


def test_sanitize_report_preserves_clean_neighbour_in_list():
    # Arrange
    report = {"examples": ["fine", f"leaked: {_API_KEY}"]}
    # Act
    clean, _ = sanitize_report(report)
    # Assert
    assert clean["examples"][0] == "fine"


def test_sanitize_report_recurses_into_nested_dict():
    # Arrange
    report = {"nested": {"inner": "all good"}}
    # Act
    clean, _ = sanitize_report(report)
    # Assert
    assert clean["nested"]["inner"] == "all good"


def test_sanitize_report_walks_tuple_values():
    # Arrange
    report = {"k": (f"{_API_KEY[:-2]}DD", "fine")}
    # Act
    clean, _ = sanitize_report(report)
    # Assert
    assert REDACTED_TOKEN in clean["k"][0]


def test_sanitize_report_preserves_tuple_shape():
    # Arrange
    report = {"k": (f"{_API_KEY}", "fine")}
    # Act
    clean, _ = sanitize_report(report)
    # Assert
    assert isinstance(clean["k"], tuple)


def test_sanitize_report_handles_scalar_input():
    # Arrange
    secret = _OAT_TOKEN
    # Act
    clean, _ = sanitize_report(secret)
    # Assert
    assert clean == REDACTED_TOKEN


def test_sanitize_report_handles_list_input():
    # Arrange
    items = ["fine", f"{_API_KEY}"]
    # Act
    clean, _ = sanitize_report(items)
    # Assert
    assert REDACTED_TOKEN in clean[1]


@pytest.mark.parametrize("keyword", ["base64", "hex", "transliterate", "translate"])
def test_system_prompt_lists_encoding_bypass(keyword):
    # Arrange
    p = KEY_PROTECTION_SYSTEM_PROMPT.lower()
    # Act
    present = keyword in p
    # Assert
    assert present, f"missing encoding-bypass keyword: {keyword}"
