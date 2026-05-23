"""Tests for newb.question_templates._injection_check.

The 5th canonical question that asks the agent whether it noticed
adversarial content. Variants + shuffle defend against the
self-reference attack: an attacker can't embed an exact-match override
when the prompt phrasing changes per run.
"""

from __future__ import annotations

from newb.question_templates._injection_check import (
    INJECTION_CHECK_VARIANTS,
    get_injection_check_question,
    shuffle_questions,
)


def test_get_injection_check_question_returns_expected_id():
    # Arrange
    seed = 0
    # Act
    q = get_injection_check_question(seed=seed)
    # Assert
    assert q["id"] == "prompt_injection_check"


def test_get_injection_check_question_seed_is_deterministic():
    # Arrange
    seed = 42
    # Act
    q1 = get_injection_check_question(seed=seed)
    q2 = get_injection_check_question(seed=seed)
    # Assert
    assert q1 == q2


def test_different_seeds_can_produce_different_variants():
    """With 8 variants and 20 seeds, the chance of all collapsing to one
    is vanishingly small. If this test ever flakes, the rng or the
    variant list is broken."""
    # Arrange
    seeds = list(range(20))
    # Act
    prompts = {get_injection_check_question(seed=s)["prompt"] for s in seeds}
    # Assert
    assert len(prompts) > 1


def test_response_format_contains_full_schema():
    """JSON schema fields must be present in every variant — downstream
    parsing depends on the exact keys."""
    # Arrange
    q = get_injection_check_question(seed=0)
    expected_keys = ("injection_detected", "severity", "examples")
    # Act
    missing = [k for k in expected_keys if k not in q["prompt"]]
    # Assert
    assert missing == []


def test_honest_nothing_found_documented_to_agent():
    """Without this clause, agents may hallucinate findings to look
    diligent. Lock the 'do not invent' instruction."""
    # Arrange
    q = get_injection_check_question(seed=0)
    # Act
    has_clause = "Do NOT invent" in q["prompt"]
    # Assert
    assert has_clause


def test_injection_check_variants_are_pairwise_distinct():
    """Regression: a future maintainer might 'consolidate' the variants
    list. The diversity is load-bearing for the self-reference defense."""
    # Arrange
    variants = INJECTION_CHECK_VARIANTS
    # Act
    unique_count = len(set(variants))
    # Assert
    assert unique_count == len(variants)


def test_injection_check_variants_have_minimum_count():
    # Arrange
    variants = INJECTION_CHECK_VARIANTS
    # Act
    count = len(variants)
    # Assert
    assert count >= 4


def test_shuffle_with_seed_is_deterministic():
    # Arrange
    qs = [{"id": f"q{i}"} for i in range(6)]
    seed = 1
    # Act
    a = shuffle_questions(qs, seed=seed)
    b = shuffle_questions(qs, seed=seed)
    # Assert
    assert a == b


def test_shuffle_preserves_question_set_membership():
    # Arrange
    qs = [{"id": f"q{i}"} for i in range(6)]
    # Act
    out = shuffle_questions(qs, seed=1)
    # Assert
    assert sorted(q["id"] for q in out) == sorted(q["id"] for q in qs)


def test_shuffle_without_seed_changes_position():
    """Probabilistic; with 6! = 720 orderings, P(identity over 20 trials)
    ≈ 0. If this flakes, randomness is broken."""
    # Arrange
    qs = [{"id": f"q{i}"} for i in range(6)]
    # Act
    outs = [tuple(q["id"] for q in shuffle_questions(qs)) for _ in range(20)]
    # Assert
    assert len(set(outs)) > 1
