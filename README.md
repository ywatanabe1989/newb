# newb

> Test your package through the eyes of a newbie agent.

A fresh AI agent reads only your `_skills/` (or equivalent docs) and tries
to use your package. If it succeeds — your docs work. If it fails — your CI
tells you why.

## Install

```bash
pip install newb
```

## Use

```bash
newb run ./src/mypkg/_skills/mypkg
newb run ./_skills --format markdown >> README.md
```

`newb run` spins up a clean docker container with **only your skills**
mounted (no host `~/.claude` leak), then asks a fresh Claude agent four
canonical questions:

1. **Identity** — "What is this package for?" / "What problems does it solve?"
2. **Usage** — "Show a working example" / "When should I NOT use this?"
3. **Boundary** — author-supplied red tests in `_red_tests.yaml`
   ("Can this do <unrelated thing>?" → must redirect, not hallucinate)

Output: JSON (for CI) or markdown (for README injection).

## Requirements

- Docker on PATH (for the agent sandbox).
- `ANTHROPIC_API_KEY` in env (used inside the container).
- Python 3.10+.

## Library API

```python
import newb

# Module-callable shortcut — for quick scripts:
report = newb("./src/mypkg/_skills/mypkg")

# Explicit form — identical behaviour, clearer intent:
report = newb.run("./src/mypkg/_skills/mypkg")

# Render the report as a README-ready markdown block:
print(newb.render_markdown(report))
```

`newb.verify` and `newb.self_explain` are backward-compat aliases for
`newb.run` (kept through one minor release; removed in 1.0).

The verb mirrors `pytest.main()` — neutral, importable, no implication
that the agent's success "proves" anything beyond what the asserts say.

## Why no aggregate "score"?

> **Principle #1: No verification without specification.**
> If you want a score, you must define what counts as correct.

Today `newb` returns the agent's actual answers (text) and per-test
boundary results (boolean from `_red_tests.yaml`). It does **not**
emit an aggregate "0.85" score because:

- A single number invites gaming (people optimise for the score, not
  for actually-better docs).
- Different tasks (description, usage, boundary) measure different
  things; averaging them is dishonest.
- Without an explicit *expected answer* per question, the "score" is
  whatever the LLM judge feels like that minute — non-reproducible.

A scoring system based on author-provided expected answers (pytest-
style discovery: `tests_newb.py` with `def test_X(agent): assert ...`)
is planned for **v0.3.0**. Until then `newb` deliberately gives you
the raw evidence and lets you decide what "good enough" means for
your package.

## Aliases

Also available as `pip install newbie-test` and `pip install agentic-test`
(same package, defensive name reservations that depend on `newb`).

## Heritage

`newb` was extracted from
[scitex-dev](https://github.com/ywatanabe1989/scitex-dev) where the
canonical integration still lives:

```bash
scitex-dev skills self-explain <package-name>
```

## License

AGPL-3.0-only. Same as the SciTeX ecosystem from which `newb` was extracted.
