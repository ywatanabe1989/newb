"""Tests for newb.question_templates._injection_check.

The 5th canonical question that asks the agent whether it noticed
adversarial content. Variants + shuffle defend against the
self-reference attack: an attacker can't embed an exact-match override
when the prompt phrasing changes per run.
"""

from __future__ import annotations

import pytest

from newb.question_templates._injection_check import (
    INJECTION_CHECK_VARIANTS,
    get_injection_check_question,
    shuffle_questions,
)


def test_returns_expected_id():
    # Arrange
    # Act
    q = get_injection_check_question(seed=0)
    # Assert
    assert q["id"] == "prompt_injection_check"


def test_same_seed_is_deterministic():
    # Arrange
    # Act
    q1 = get_injection_check_question(seed=42)
    q2 = get_injection_check_question(seed=42)
    # Assert
    assert q1 == q2


def test_different_seeds_can_produce_different_variants():
    # Arrange
    seeds = list(range(20))
    # Act
    prompts = {get_injection_check_question(seed=s)["prompt"] for s in seeds}
    # Assert
    assert len(prompts) > 1


@pytest.mark.parametrize("key", ["injection_detected", "severity", "examples"])
def test_response_format_contains_schema_key(key):
    # Arrange
    q = get_injection_check_question(seed=0)
    # Act
    present = key in q["prompt"]
    # Assert
    assert present


def test_honest_nothing_found_documented_to_agent():
    # Arrange
    q = get_injection_check_question(seed=0)
    # Act
    has_clause = "Do NOT invent" in q["prompt"]
    # Assert
    assert has_clause


def test_variants_are_all_distinct():
    # Arrange
    # Act
    distinct = len(set(INJECTION_CHECK_VARIANTS))
    # Assert
    assert distinct == len(INJECTION_CHECK_VARIANTS)


def test_variants_count_is_at_least_four():
    # Arrange
    # Act
    count = len(INJECTION_CHECK_VARIANTS)
    # Assert
    assert count >= 4


def test_shuffle_with_seed_is_deterministic():
    # Arrange
    qs = [{"id": f"q{i}"} for i in range(6)]
    # Act
    a = shuffle_questions(qs, seed=1)
    b = shuffle_questions(qs, seed=1)
    # Assert
    assert a == b


def test_shuffle_preserves_the_id_set():
    # Arrange
    qs = [{"id": f"q{i}"} for i in range(6)]
    # Act
    out = shuffle_questions(qs, seed=1)
    # Assert
    assert sorted(q["id"] for q in out) == sorted(q["id"] for q in qs)


def test_shuffle_without_seed_changes_position():
    # Arrange
    qs = [{"id": f"q{i}"} for i in range(6)]
    # Act
    outs = [tuple(q["id"] for q in shuffle_questions(qs)) for _ in range(20)]
    # Assert
    assert len(set(outs)) > 1
