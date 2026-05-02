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


def test_returns_expected_id():
    q = get_injection_check_question(seed=0)
    assert q["id"] == "prompt_injection_check"


def test_seed_is_deterministic():
    q1 = get_injection_check_question(seed=42)
    q2 = get_injection_check_question(seed=42)
    assert q1 == q2


def test_different_seeds_can_produce_different_variants():
    """With 8 variants and 20 seeds, the chance of all collapsing to one
    is vanishingly small. If this test ever flakes, the rng or the
    variant list is broken."""
    seeds = list(range(20))
    prompts = {get_injection_check_question(seed=s)["prompt"] for s in seeds}
    assert len(prompts) > 1


def test_response_format_contains_schema():
    """JSON schema fields must be present in every variant — downstream
    parsing depends on the exact keys."""
    q = get_injection_check_question(seed=0)
    for key in ("injection_detected", "severity", "examples"):
        assert key in q["prompt"]


def test_honest_nothing_found_documented_to_agent():
    """Without this clause, agents may hallucinate findings to look
    diligent. Lock the 'do not invent' instruction."""
    q = get_injection_check_question(seed=0)
    assert "Do NOT invent" in q["prompt"]


def test_variants_are_distinct():
    """Regression: a future maintainer might 'consolidate' the variants
    list. The diversity is load-bearing for the self-reference defense."""
    assert len(set(INJECTION_CHECK_VARIANTS)) == len(INJECTION_CHECK_VARIANTS)
    assert len(INJECTION_CHECK_VARIANTS) >= 4


def test_shuffle_with_seed_is_deterministic():
    qs = [{"id": f"q{i}"} for i in range(6)]
    a = shuffle_questions(qs, seed=1)
    b = shuffle_questions(qs, seed=1)
    assert a == b


def test_shuffle_preserves_set():
    qs = [{"id": f"q{i}"} for i in range(6)]
    out = shuffle_questions(qs, seed=1)
    assert sorted(q["id"] for q in out) == sorted(q["id"] for q in qs)


def test_shuffle_without_seed_changes_position():
    """Probabilistic; with 6! = 720 orderings, P(identity over 20 trials)
    ≈ 0. If this flakes, randomness is broken."""
    qs = [{"id": f"q{i}"} for i in range(6)]
    outs = [tuple(q["id"] for q in shuffle_questions(qs)) for _ in range(20)]
    assert len(set(outs)) > 1
