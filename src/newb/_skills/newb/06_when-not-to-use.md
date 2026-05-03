---
description: |
  [TOPIC] When Not To Use
  [DETAILS] Explicit boundaries — newb is not a unit-test runner, not a model benchmark, not a coverage tool, not a security scanner, and not deterministic. Use the right tool for those jobs and reach for newb only for docs-quality verification.
tags: [newb-when-not-to-use]
---

# When NOT to use newb

newb verifies one thing: **whether your docs are sufficient for an
agent that has never seen your package**. Reach for a different tool
for any of the following:

| Job | Use | Why not newb |
|---|---|---|
| Run unit tests / integration tests | `pytest` (or your test framework) | newb's "test" is "can the agent answer questions"; it never executes your package's code. |
| Measure code coverage | `pytest-cov`, `coverage.py` | Same — no execution, no coverage signal. |
| Benchmark a Claude model's reasoning | `inspect-ai`, `lm-evaluation-harness` | newb conflates docs quality with model capability; bench frameworks isolate the model. |
| Adversarial security testing of an agent | red-team frameworks, `garak` | newb only grants `Read`; it doesn't probe prompt-injection, data exfiltration, or tool abuse. |
| Grade prose quality or style | human review, `vale` | newb checks comprehension by an LLM, not editorial quality. |
| Verify code examples actually run | doctest / pytest with `--doctest-modules` | newb may report "quick_start present" while the example fails on execution — it never runs anything. |

## Determinism caveat

LLM responses are non-deterministic. A passing newb run today may fail
tomorrow with the same docs and the same model — drift is small but
real. Strategies for stable CI:

- `--runs 3` (or higher) and gate on majority pass
- Pair `expect_contains` (deterministic substring) with a `judge:`
  criterion (semantic) — the AND of the two reduces flake
- Pin `--model` explicitly (don't rely on the default)
- Re-run on failure before failing the build (transient SDK timeouts)

## Auth caveat

newb owns its own env namespace (`NEWB_ANTHROPIC_API_KEY`) and never
silently inherits the upstream `ANTHROPIC_API_KEY` — set the NEWB_-
prefixed var explicitly to opt in.

The container runtimes hard-fail if `NEWB_ANTHROPIC_API_KEY` is unset
(no OAuth fallback inside containers). The `host` runtime falls
through to `~/.claude/` OAuth login when the env var is unset, which
is a personal-use gray zone per Anthropic's commercial ToS — for
redistributed / CI use, set `NEWB_ANTHROPIC_API_KEY`.

## Surface limit

newb reads only `.md` files (recursively, via `Path.rglob("*.md")`).
Docs in `.rst`, `.org`, `.ipynb`, raw HTML, or generated Sphinx output
are invisible to it. If your package's docs live in another format,
either:

- generate `.md` exports for the agent's view, or
- point newb at a curated `_skills/<pkg>/` tree built specifically for
  agent consumption (recommended).
