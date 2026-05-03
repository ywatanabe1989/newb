# Newb badge — how to add `Newb | passing` to your package's README

newb's CI workflow gives every package a passing/failing badge that
reflects whether a fresh AI agent can install + use your package from
your docs alone. This is the same workflow newb runs against itself
(see [self-verify](../.github/workflows/newb-self-verify.yml)).

## TL;DR

1. Drop the workflow file (below) at `.github/workflows/newb.yml`.
2. Set repo / org secret `NEWB_ANTHROPIC_API_KEY` (any
   `sk-ant-api03-…` API key or `sk-ant-oat01-…` OAuth token).
3. Trigger once manually from the Actions tab to confirm green.
4. Add the badge to your README (markdown one-liner below).

After that, every workflow_dispatch (or schedule, or PR-on-docs-paths
trigger when you flip them on) emits an updated badge.

## Workflow template (`.github/workflows/newb.yml`)

```yaml
name: Newb

on:
  workflow_dispatch:

jobs:
  newb:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    permissions:
      contents: read
      packages: read       # pull ghcr.io/ywatanabe1989/newb-runner
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Login to ghcr.io (so docker can pull the runner image)
        run: |
          echo "${{ secrets.GHCR_PAT }}" \
            | docker login ghcr.io -u ywatanabe1989 --password-stdin

      - name: Install newb
        run: pip install --upgrade newb

      - name: Run newb
        env:
          NEWB_ANTHROPIC_API_KEY: ${{ secrets.NEWB_ANTHROPIC_API_KEY }}
          NEWB_HARDEN_MEMORY: 4g
          NEWB_HARDEN_PIDS_LIMIT: 512
          NEWB_HARDEN_CPUS: "2"
        run: |
          if [ -z "${NEWB_ANTHROPIC_API_KEY}" ]; then
            echo "::error::secrets.NEWB_ANTHROPIC_API_KEY is not set." >&2
            exit 1
          fi
          newb . --json -vv > newb-report.json

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v7
        with:
          name: newb-report
          path: newb-report.json
          if-no-files-found: warn

      - name: Render markdown summary
        if: success()
        run: |
          python - <<'PY' >> "$GITHUB_STEP_SUMMARY"
          import json, newb
          with open("newb-report.json") as f:
              report = json.load(f)
          print(newb.render_markdown(report))
          PY
```

Note the `name: Newb` — that string is what GitHub renders on the
badge. Keeping it consistent across packages makes the visual signal
recognizable.

## Badge markdown for your README

```markdown
[![Newb](https://github.com/<owner>/<repo>/actions/workflows/newb.yml/badge.svg?branch=<branch>)](https://github.com/<owner>/<repo>/actions/workflows/newb.yml)
```

Typical placement is alongside your other CI/PyPI badges (under the
project tagline, before the description body).

## Required secret

| Secret | Source | Notes |
|---|---|---|
| `NEWB_ANTHROPIC_API_KEY` | Anthropic API key OR Claude Code OAuth access token | newb forwards verbatim; the Anthropic backend accepts both on the same Authorization header. For CI, prefer a real API key with a per-key spend cap (Pro/Max OAuth tokens expire and Pro/Max licenses aren't sized for automated use). |
| `GHCR_PAT` | ywatanabe1989's GHCR-scoped PAT | Needed only because the runner image is currently a private package. If we make it public later, this requirement drops. |

For SciTeX-ecosystem repos, the cleanest pattern is an **org-level**
`NEWB_ANTHROPIC_API_KEY` secret on `ywatanabe1989`, visible to all
selected repos. One secret to rotate.

## Triggers — start manual, scale up

The template above ships with `workflow_dispatch` only — no `schedule`,
no `pull_request:` — so the first run is deliberately manual and you
control when API spend happens.

When the canary is stable, common patterns to add:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "13 2 * * *"          # daily at a hash-of-package-name slot (avoid all-at-once)
  pull_request:
    paths:
      - "README.md"
      - "_skills/**"
      - "docs/**"
      - "src/**/__init__.py"
      - "pyproject.toml"
```

`paths:` keeps PR-time runs to actual docs-affecting changes, so
ordinary code PRs don't pay the 5-minute API cost.

## Cost shape

Per-run rough numbers (measured against scitex-io and newb itself, on
GitHub-hosted Ubuntu runners):

- Wall-clock: ~3-5 minutes
- API spend on `claude-haiku-4-5`: ~$0.05-$0.15 per run
- CI minutes: free for public repos

Across the SciTeX 19-package ecosystem at one daily run per package,
that's ~$30-90/month in API spend, $0 in CI minutes. See the
[security model](../SECURITY.md) for why this is the right
shape.

## Failure semantics

The workflow is green when:
- newb produced a report (i.e. the SDK call completed end-to-end), AND
- all workflow steps exited 0.

The workflow is **not** gated on the *content* of the report — a
report that says `INSTALL: fail` will still produce a green workflow
and a `Newb | passing` badge. This is by design: newb's value is in
the *evidence*, not in a binary verdict. Read the
`newb-report.json` artifact (or the markdown summary) to see what
actually happened. If you want hard-gating, wrap the run with `jq`
(see `_skills/newb/07_ci-integration.md`).
