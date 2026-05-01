# 🐝 newb

> Test your package through the eyes of a newbie agent.

<p align="center"><img src="./assets/newb-logo.png" width="220" alt="newb mascot"/></p>

A fresh AI agent reads only your `_skills/` (or equivalent docs) and tries
to use your package. If it succeeds, your docs work.

## Install

```bash
pip install newb
```

## Use

```bash
newb ./src/mypkg/_skills/mypkg
newb ./_skills --format markdown >> README.md
```

Spins up a clean docker container with **only your skills** mounted, then
asks a fresh Claude agent four canonical questions (what for / problems /
quick start / when not to use), plus optional red tests from
`_red_tests.yaml`.

Output: JSON (for CI) or markdown (for README injection).

## Library

```python
import newb
report = newb("./src/mypkg/_skills/mypkg")
print(newb.render_markdown(report))
```

## Requirements

- Docker on PATH
- `ANTHROPIC_API_KEY` in env
- Python 3.10+

## No aggregate score

> **No verification without specification.**

`newb` returns raw answers, not a "0.85". Author-defined expected
answers (pytest-style `tests_newb.py`) are planned for v0.4.0+.

## Aliases

`pip install newbie-test` and `pip install agentic-test` both depend on
`newb` — defensive name reservations.

## Heritage

Extracted from [scitex-dev](https://github.com/ywatanabe1989/scitex-dev),
where `scitex-dev skills self-explain <pkg>` is the canonical integration.

## License

AGPL-3.0-only.
