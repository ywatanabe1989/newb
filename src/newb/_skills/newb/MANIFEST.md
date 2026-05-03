---
description: |
  [TOPIC] Manifest
  [DETAILS] Skills Manifest — These skills are distributed with **newb** and are the source of truth.
tags: [newb-manifest]
---

# Skills Manifest

These skills are distributed with **newb** and are the source of truth.
Local copies of these files (e.g. under `~/.claude/skills/`) may be
overwritten when newb updates.

## Update

```bash
pip install --upgrade newb
```

## Layout

| File | Purpose |
|---|---|
| `SKILL.md`               | Thin index + tagline + when-to-reach-for-newb table |
| `01_quick-start.md`      | Install + minimal CLI + Python forms + output shape |
| `02_canonical-questions.md` | The 6-question templates + few-shot + `newb-json` trailer |
| `03_author-tests.md`     | `tests_newb.yaml` schema + double grading semantics |
| `04_isolation-runtimes.md` | docker / podman / apptainer; container = boundary, not SDK |
| `05_source-resolution.md` | Local paths, git URLs, project-root auto-detect |
| `06_when-not-to-use.md`  | Explicit boundaries + determinism caveat |
| `07_ci-integration.md`   | JSON / markdown output, `<key>_parsed`, `newb gate` |
| `08_ci-badge.md`         | `Newb \| passing` GitHub Actions badge adoption |
| `30_env-vars.md`         | NEWB_-prefixed env vars (auth, image, model, cwd, …) |
