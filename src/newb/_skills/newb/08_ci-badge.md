---
name: newb-ci-badge
description: How a Python package adopts the `Newb | passing` GitHub Actions badge — the workflow file template, the `NEWB_ANTHROPIC_API_KEY` secret, and the README markdown one-liner. Reuses the same self-verify scaffold newb runs against itself, so a repo gains a visible "an AI agent can use this package's docs" signal in ~5 minutes.
tags: [newb, ci]
---

# `Newb | passing` badge — adoption checklist

Three steps for any Python package that wants the badge:

1. **Workflow** — drop a `.github/workflows/newb.yml` at the
   conventional path. Use `name: Newb` so the badge label is
   consistent across packages.
2. **Secret** — set `NEWB_ANTHROPIC_API_KEY` (real API key or OAuth
   access token; newb accepts both on the same Authorization header).
   Org-level secret if you're rolling out to many repos.
3. **README badge** — paste the markdown image below and replace
   `<owner>` / `<repo>` / `<branch>`.

The full canonical template (workflow YAML, secret notes, trigger
patterns, cost shape, failure semantics) lives in
[`docs/badge.md`](https://github.com/ywatanabe1989/newb/blob/main/docs/badge.md). This leaf is the
discovery shim — agents and humans landing on the skill get the
4-line summary plus the pointer.

## README badge markdown

```markdown
[![Newb](https://github.com/<owner>/<repo>/actions/workflows/newb.yml/badge.svg?branch=<branch>)](https://github.com/<owner>/<repo>/actions/workflows/newb.yml)
```

The label `Newb` comes from the workflow's `name:` field — keep it
verbatim across packages so the visual signal is recognizable.

## Convention: name the workflow `Newb`, name the file `newb.yml`

```yaml
# .github/workflows/newb.yml
name: Newb
on:
  workflow_dispatch:
# ... see docs/badge.md for the full body
```

Two consistency reasons:

1. **Badge label** — GH's native badge renders the workflow `name:`
   value. Mixed names (`newb verifies itself` vs `newb docs check`)
   would produce inconsistent badges across the ecosystem.
2. **`paths:` filter discovery** — when packages later flip on
   PR-triggered runs (`paths: [README.md, _skills/**, docs/**]`),
   keeping the file name predictable lets ecosystem-wide tooling
   target it (`scitex-dev` or similar).

## What a green badge means

It means: **the workflow ran end-to-end and produced a report.** It
does **not** mean every canonical question passed — `INSTALL: fail`
inside the report still ships a green badge. The badge attests to
"newb can run against this package", not "this package's docs are
perfect".

For hard-gating ("fail CI if `INSTALL: fail`"), append a `newb gate`
step after the run:

```yaml
      - name: Gate on report
        run: newb gate newb-report.json
```

Default criteria require `install==ok`, `import==ok`, and
`prompt_injection_check.found==false`. Override per-project via
`[tool.newb.gate]` in `pyproject.toml`. See
[`docs/badge.md`](https://github.com/ywatanabe1989/newb/blob/main/docs/badge.md)
for the full schema, or
[`07_ci-integration.md`](07_ci-integration.md) for the legacy `jq`
pattern.

## Cost / spend shape

- Wall-clock per run: ~3-5 minutes (most in `post_install_check`).
- API spend per run on `claude-haiku-4-5`: ~$0.05-$0.15.
- CI minutes: free for public repos.

Default trigger is `workflow_dispatch` (manual). Add `schedule:` /
`pull_request:` only after the canary is stable — see
[`docs/badge.md`](https://github.com/ywatanabe1989/newb/blob/main/docs/badge.md) for the recommended
hash-of-package-name cron-slot pattern that staggers ecosystem-wide
runs.
