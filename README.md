# newb

> Test your package through the eyes of a newbie agent.

A fresh AI agent reads only your `_skills/` (or equivalent docs) and tries
to use your package. If it succeeds — your docs work. If it fails — your CI
tells you why.

## Status

`0.0.1` — name reservation + placeholder. Active development is happening
inside [scitex-dev](https://github.com/ywatanabe1989/scitex-dev) under
`scitex-dev skills self-explain`. The standalone `newb` package will land
once the API stabilizes (~2-4 weeks).

## Try the prototype today

```bash
pip install scitex-dev[cli]
scitex-dev skills self-explain <your-package>
```

## What it will do (when fleshed out)

```bash
pip install newb
newb verify ./my-package
```

The agent will be asked, against ONLY the package's docs:

1. **Comprehension** — "What is this for?" / "What problems does it solve?"
2. **Execution** — "Show a working example" / "When should I NOT use this?"
3. **Boundary** — "Can this do <unrelated thing>?" → must redirect, not hallucinate

Results render as JSON (for CI) or markdown (for README injection).

## Aliases

Also available as `pip install newbie-test` and `pip install agentic-test`
(same package, just defensive name reservations).

## License

AGPL-3.0-only. Same as the SciTeX ecosystem from which `newb` was
extracted.
