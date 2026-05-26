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


# ---------------------------------------------------------------------------
# `sanitize` — clean text passes through. Split per facet.
# ---------------------------------------------------------------------------


@pytest.fixture
def _clean_sanitize():
    return sanitize("Just a normal package description.")


def test_sanitize_clean_text_not_leaked(_clean_sanitize):
    # Arrange
    r = _clean_sanitize
    # Act
    flag = r.leaked
    # Assert
    assert flag is False


def test_sanitize_clean_text_preserves_input(_clean_sanitize):
    # Arrange
    r = _clean_sanitize
    # Act
    out = r.text
    # Assert
    assert out == "Just a normal package description."


def test_sanitize_clean_text_yields_no_matches(_clean_sanitize):
    # Arrange
    r = _clean_sanitize
    # Act
    out = r.matches
    # Assert
    assert out == []


# ---------------------------------------------------------------------------
# Plaintext sk-ant-api03-* — three facets split.
# ---------------------------------------------------------------------------


@pytest.fixture
def _plaintext_key_sanitize():
    text = "The key is sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA done."
    return sanitize(text)


def test_sanitize_plaintext_api_key_flagged_leaked(_plaintext_key_sanitize):
    # Arrange
    r = _plaintext_key_sanitize
    # Act
    flag = r.leaked
    # Assert
    assert flag is True


def test_sanitize_plaintext_api_key_text_contains_redaction(
    _plaintext_key_sanitize,
):
    # Arrange
    r = _plaintext_key_sanitize
    # Act
    has_token = REDACTED_TOKEN in r.text
    # Assert
    assert has_token


def test_sanitize_plaintext_api_key_text_strips_original_key(
    _plaintext_key_sanitize,
):
    # Arrange
    r = _plaintext_key_sanitize
    # Act
    still_present = "sk-ant-api03" in r.text
    # Assert
    assert still_present is False


def test_sanitize_plaintext_api_key_matches_include_plaintext_rule(
    _plaintext_key_sanitize,
):
    # Arrange
    r = _plaintext_key_sanitize
    # Act
    matched = "anthropic_api_key_plaintext" in r.matches
    # Assert
    assert matched


# ---------------------------------------------------------------------------
# OAuth (oat01) tokens — two facets.
# ---------------------------------------------------------------------------


@pytest.fixture
def _oat_token_sanitize():
    text = "Token: sk-ant-oat01-BBBBBBBBBBBBBBBBBBBBBBBBBBBB."
    return sanitize(text)


def test_sanitize_oat_token_flagged_leaked(_oat_token_sanitize):
    # Arrange
    r = _oat_token_sanitize
    # Act
    flag = r.leaked
    # Assert
    assert flag is True


def test_sanitize_oat_token_matches_include_plaintext_rule(_oat_token_sanitize):
    # Arrange
    r = _oat_token_sanitize
    # Act
    matched = "anthropic_api_key_plaintext" in r.matches
    # Assert
    assert matched


def test_sanitize_short_placeholder_not_matched():
    """``sk-ant-api03-...`` (3-dot placeholder) is documentation, not a leak."""
    # Arrange
    text = "Set NEWB_ANTHROPIC_API_KEY to sk-ant-api03-..."
    # Act
    r = sanitize(text)
    # Assert
    assert r.leaked is False, f"placeholder should not match, got {r.matches}"


# ---------------------------------------------------------------------------
# Base64-prefix detection.
# ---------------------------------------------------------------------------


@pytest.fixture
def _base64_prefix_sanitize():
    text = (
        "encoded: c2stYW50LWFwaTAzLUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB"
        "QUFBQUFBQUFBQUFBQUFB= end"
    )
    return sanitize(text)


def test_sanitize_base64_prefix_flagged_leaked(_base64_prefix_sanitize):
    """Catches encoded leaks where the agent base64'd the key as bypass."""
    # Arrange
    r = _base64_prefix_sanitize
    # Act
    flag = r.leaked
    # Assert
    assert flag is True


def test_sanitize_base64_prefix_matches_include_base64_rule(
    _base64_prefix_sanitize,
):
    # Arrange
    r = _base64_prefix_sanitize
    # Act
    matched = "anthropic_api_key_base64_prefix" in r.matches
    # Assert
    assert matched


# ---------------------------------------------------------------------------
# sanitize_report — walking dict + list values.
# ---------------------------------------------------------------------------


@pytest.fixture
def _walked_dict_and_list():
    report = {
        "what_for": "A clean description.",
        "examples": [
            "fine",
            "leaked: sk-ant-api03-CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        ],
        "nested": {"inner": "all good"},
    }
    return sanitize_report(report)


def test_sanitize_report_redacts_leaked_list_element(_walked_dict_and_list):
    # Arrange
    clean, _ = _walked_dict_and_list
    # Act
    has_token = REDACTED_TOKEN in clean["examples"][1]
    # Assert
    assert has_token


def test_sanitize_report_preserves_clean_list_element(_walked_dict_and_list):
    # Arrange
    clean, _ = _walked_dict_and_list
    # Act
    value = clean["examples"][0]
    # Assert
    assert value == "fine"


def test_sanitize_report_preserves_clean_nested_dict(_walked_dict_and_list):
    # Arrange
    clean, _ = _walked_dict_and_list
    # Act
    value = clean["nested"]["inner"]
    # Assert
    assert value == "all good"


def test_sanitize_report_matches_include_plaintext_rule(_walked_dict_and_list):
    # Arrange
    _, matches = _walked_dict_and_list
    # Act
    matched = "anthropic_api_key_plaintext" in matches
    # Assert
    assert matched


# ---------------------------------------------------------------------------
# Tuple-walk regression.
# ---------------------------------------------------------------------------


@pytest.fixture
def _walked_tuple():
    """Regression: tuple values were being skipped, secrets passed through.

    Fixed during 0.11 QA. Lock in with this test.
    """
    report = {"k": ("sk-ant-api03-DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD", "fine")}
    return sanitize_report(report)


def test_sanitize_report_preserves_tuple_shape(_walked_tuple):
    # Arrange
    clean, _ = _walked_tuple
    # Act
    shape = type(clean["k"])
    # Assert
    assert shape is tuple, "tuple shape preserved"


def test_sanitize_report_redacts_secret_inside_tuple(_walked_tuple):
    # Arrange
    clean, _ = _walked_tuple
    # Act
    has_token = REDACTED_TOKEN in clean["k"][0]
    # Assert
    assert has_token


def test_sanitize_report_preserves_clean_tuple_sibling(_walked_tuple):
    # Arrange
    clean, _ = _walked_tuple
    # Act
    value = clean["k"][1]
    # Assert
    assert value == "fine"


def test_sanitize_report_tuple_matches_include_plaintext_rule(_walked_tuple):
    # Arrange
    _, matches = _walked_tuple
    # Act
    matched = "anthropic_api_key_plaintext" in matches
    # Assert
    assert matched


# ---------------------------------------------------------------------------
# Scalar / list top-level inputs.
# ---------------------------------------------------------------------------


@pytest.fixture
def _scalar_input_walked():
    """Top-level scalar (not dict) shouldn't crash; secrets still scrubbed."""
    return sanitize_report("sk-ant-oat01-EEEEEEEEEEEEEEEEEEEEEEEEEEEE")


def test_sanitize_report_scalar_input_clean_is_redaction_token(
    _scalar_input_walked,
):
    # Arrange
    clean, _ = _scalar_input_walked
    # Act
    value = clean
    # Assert
    assert value == REDACTED_TOKEN


def test_sanitize_report_scalar_input_matches_include_plaintext_rule(
    _scalar_input_walked,
):
    # Arrange
    _, matches = _scalar_input_walked
    # Act
    matched = "anthropic_api_key_plaintext" in matches
    # Assert
    assert matched


@pytest.fixture
def _list_input_walked():
    return sanitize_report(["fine", "sk-ant-api03-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"])


def test_sanitize_report_list_input_preserves_clean_element(_list_input_walked):
    # Arrange
    clean, _ = _list_input_walked
    # Act
    value = clean[0]
    # Assert
    assert value == "fine"


def test_sanitize_report_list_input_redacts_leaked_element(_list_input_walked):
    # Arrange
    clean, _ = _list_input_walked
    # Act
    has_token = REDACTED_TOKEN in clean[1]
    # Assert
    assert has_token


def test_sanitize_report_list_input_matches_include_plaintext_rule(
    _list_input_walked,
):
    # Arrange
    _, matches = _list_input_walked
    # Act
    matched = "anthropic_api_key_plaintext" in matches
    # Assert
    assert matched


# ---------------------------------------------------------------------------
# System-prompt bypass-keyword pinning. Split per keyword (parametrize).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "keyword", ["base64", "hex", "transliterate", "translate"]
)
def test_system_prompt_lists_encoding_bypass_keyword(keyword):
    """Regression: shortening this block re-opens encoding-bypass attacks.

    Pin each explicit keyword — base64, hex, transliterate, translate are
    the four that adaptive injection commonly frames as 'just transform
    this innocuous value'.
    """
    # Arrange
    prompt_lower = KEY_PROTECTION_SYSTEM_PROMPT.lower()
    # Act
    present = keyword in prompt_lower
    # Assert
    assert present, f"missing encoding-bypass keyword: {keyword}"
