"""Tests for newb._sanitizer.

Migrated from the third-party audit drop's
test_security_0_11.py::TestSanitizer block, with the tuple-walk
regression added for the bug found during QA review.
"""

from __future__ import annotations


from newb._sanitizer import (
    KEY_PROTECTION_SYSTEM_PROMPT,
    REDACTED_TOKEN,
    sanitize,
    sanitize_report,
)


def test_clean_text_passes_through():
    r = sanitize("Just a normal package description.")
    assert not r.leaked
    assert r.text == "Just a normal package description."
    assert r.matches == []


def test_plaintext_api_key_redacted():
    text = "The key is sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA done."
    r = sanitize(text)
    assert r.leaked
    assert REDACTED_TOKEN in r.text
    assert "sk-ant-api03" not in r.text
    assert "anthropic_api_key_plaintext" in r.matches


def test_oat_token_redacted():
    text = "Token: sk-ant-oat01-BBBBBBBBBBBBBBBBBBBBBBBBBBBB."
    r = sanitize(text)
    assert r.leaked
    assert "anthropic_api_key_plaintext" in r.matches


def test_short_placeholder_not_matched():
    """``sk-ant-api03-...`` (3-dot placeholder) is documentation, not a leak."""
    text = "Set NEWB_ANTHROPIC_API_KEY to sk-ant-api03-..."
    r = sanitize(text)
    assert not r.leaked, f"placeholder should not match, got {r.matches}"


def test_base64_prefix_redacted():
    """Catches encoded leaks where the agent base64'd the key as bypass."""
    text = (
        "encoded: c2stYW50LWFwaTAzLUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB"
        "QUFBQUFBQUFBQUFBQUFB= end"
    )
    r = sanitize(text)
    assert r.leaked
    assert "anthropic_api_key_base64_prefix" in r.matches


def test_sanitize_report_walks_dict_and_list():
    report = {
        "what_for": "A clean description.",
        "examples": [
            "fine",
            "leaked: sk-ant-api03-CCCCCCCCCCCCCCCCCCCCCCCCCCCC",
        ],
        "nested": {"inner": "all good"},
    }
    clean, matches = sanitize_report(report)
    assert REDACTED_TOKEN in clean["examples"][1]
    assert clean["examples"][0] == "fine"
    assert clean["nested"]["inner"] == "all good"
    assert "anthropic_api_key_plaintext" in matches


def test_sanitize_report_walks_tuple():
    """Regression: tuple values were being skipped, secrets passed through.

    Fixed during 0.11 QA. Lock in with this test.
    """
    report = {"k": ("sk-ant-api03-DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD", "fine")}
    clean, matches = sanitize_report(report)
    assert isinstance(clean["k"], tuple), "tuple shape preserved"
    assert REDACTED_TOKEN in clean["k"][0]
    assert clean["k"][1] == "fine"
    assert "anthropic_api_key_plaintext" in matches


def test_sanitize_report_handles_scalar_input():
    """Top-level scalar (not dict) shouldn't crash; secrets still scrubbed."""
    clean, matches = sanitize_report("sk-ant-oat01-EEEEEEEEEEEEEEEEEEEEEEEEEEEE")
    assert clean == REDACTED_TOKEN
    assert "anthropic_api_key_plaintext" in matches


def test_sanitize_report_handles_list_input():
    clean, matches = sanitize_report(
        ["fine", "sk-ant-api03-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"]
    )
    assert clean[0] == "fine"
    assert REDACTED_TOKEN in clean[1]
    assert "anthropic_api_key_plaintext" in matches


def test_system_prompt_lists_encoding_bypasses():
    """Regression: shortening this block re-opens encoding-bypass attacks.

    Pin the explicit list — base64, hex, transliterate, translate are
    the four that adaptive injection commonly frames as 'just transform
    this innocuous value'.
    """
    p = KEY_PROTECTION_SYSTEM_PROMPT.lower()
    for keyword in ("base64", "hex", "transliterate", "translate"):
        assert keyword in p, f"missing encoding-bypass keyword: {keyword}"
