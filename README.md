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
newb verify ./src/mypkg/_skills/mypkg
newb verify ./_skills --format markdown >> README.md
```

`newb verify` spins up a clean docker container with **only your skills**
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
from pathlib import Path
import newb

result = newb.self_explain(Path("./src/mypkg/_skills/mypkg"))
print(newb.render_markdown(result))
```

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
