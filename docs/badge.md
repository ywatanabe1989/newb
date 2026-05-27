# Newb badge — how to add `Newb | passing` to your package's README

newb's CI workflow gives every package a passing/failing badge that
reflects whether a fresh AI agent can install + use your package from
your docs alone. This is the same workflow newb runs against itself
(see [self-verify](../.github/workflows/newb-self-verify.yml)).

## TL;DR

1. Drop the workflow file (below) at `.github/workflows/newb.yml`.
2. Set exactly one of these repo / org secrets:
   - `NEWB_ANTHROPIC_API_KEY` — `sk-ant-api03-…` real API key
     (per-token billing).
   - `NEWB_CLAUDE_CODE_CREDENTIALS_JSON` — full
     `~/.claude/.credentials.json` content for OAuth flat-rate
     (Claude Code Pro / Max). Required for `sk-ant-oat01-…` tokens
     — Anthropic rejects them bare without refresh-token /
     expiresAt context.
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
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      - name: Install newb
        run: pip install --upgrade newb

      - name: Run newb
        env:
          # Set exactly one — real `sk-ant-api*` keys work as a bare
          # env var (per-token billing).
          NEWB_ANTHROPIC_API_KEY: ${{ secrets.NEWB_ANTHROPIC_API_KEY }}
          # OAuth flat-rate (Claude Code Pro/Max): pass the full
          # ~/.claude/.credentials.json content as a secret. newb
          # materialises it to a tempfile and bind-mounts it into
          # the container so the SDK uses the file-based credentials_file
          # flow (Anthropic rejects sk-ant-oat01-… tokens passed as
          # bare env). Leave unset for sk-ant-api* keys.
          NEWB_CLAUDE_CODE_CREDENTIALS_JSON: ${{ secrets.NEWB_CLAUDE_CODE_CREDENTIALS_JSON }}
          NEWB_HARDEN_MEMORY: 4g
          NEWB_HARDEN_PIDS_LIMIT: 512
          NEWB_HARDEN_CPUS: "2"
        run: |
          if [ -z "${NEWB_ANTHROPIC_API_KEY}" ] && [ -z "${NEWB_CLAUDE_CODE_CREDENTIALS_JSON}" ]; then
            echo "::error::Neither secrets.NEWB_ANTHROPIC_API_KEY nor secrets.NEWB_CLAUDE_CODE_CREDENTIALS_JSON is set on this repo." >&2
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

      - name: Gate on report (optional — uncomment to hard-fail on regressions)
        # run: newb gate newb-report.json
        run: 'true'

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

## Required secrets

Set exactly one of:

| Secret | When | Notes |
|---|---|---|
| `NEWB_ANTHROPIC_API_KEY` | per-token billing | Real Anthropic API key (`sk-ant-api03-…`). For CI, prefer this with a per-key spend cap. Bare OAuth tokens (`sk-ant-oat01-…`) will NOT work here — use the credentials-json secret below. |
| `NEWB_CLAUDE_CODE_CREDENTIALS_JSON` | OAuth flat-rate (Claude Code Pro / Max) | Full `~/.claude/.credentials.json` content (the file `claude /login` writes locally — refresh_token + accessToken + expiresAt + scopes + subscriptionType). newb materialises it to a tempfile and bind-mounts it into the container so the SDK uses the file-based credentials_file flow. Anthropic rejects bare `sk-ant-oat01-…` tokens; this is the supported OAuth path. |

The runner image (`ghcr.io/ywatanabe1989/newb-runner`) is published
publicly, so no docker login step is required.

If you're rolling out across many repos under one org, set the chosen
secret once as an organization secret with selected-repo access — one
place to rotate.

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

Per-run rough numbers, measured on GitHub-hosted Ubuntu runners:

- Wall-clock: ~3-5 minutes
- API spend on `claude-haiku-4-5`: ~$0.05-$0.15 per run
- CI minutes: free for public repos

For N packages on a daily schedule, multiply: ~N × $0.05-$0.15/day in
API spend, $0 in CI minutes. See the
[security model](../SECURITY.md) for why this shape is intentional.

## Failure semantics

The workflow is green when:
- newb produced a report (i.e. the SDK call completed end-to-end), AND
- all workflow steps exited 0.

By default the workflow is **not** gated on the *content* of the
report — a report that says `INSTALL: fail` will still produce a
green workflow and a `Newb | passing` badge. This is by design:
newb's value is in the *evidence*, not in a binary verdict.

If you DO want hard-gating, append a `newb gate` step:

```yaml
      - name: Gate on report
        run: newb gate newb-report.json
```

Default criteria:

- `post_install_check.install == "ok"`
- `post_install_check.import  == "ok"`
- `prompt_injection_check.found == false`

Override per-project in `pyproject.toml`:

```toml
[tool.newb.gate.post_install_check]
install = "ok"
import  = "ok"
cli     = ["ok", "n/a"]   # list = any-of

[tool.newb.gate.prompt_injection_check]
found = false
```

The gate reads `<key>_parsed` fields, populated by host-side parsers —
backed by the agent's fenced ` ```newb-json ` trailer when present,
regex over the prose otherwise.
