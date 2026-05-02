---
package: newb
version: 0.9.0
source: github.com/ywatanabe1989/newb
skills_path: src/newb/_skills/newb/
name: MANIFEST
tags: [newb, scitex-package]
description: Skills Manifest — These skills are distributed with **newb** and are the source of truth.
---

# Skills Manifest

These skills are distributed with **newb** and are the source of truth.
Local edits at `~/.claude/skills/scitex/newb/` may be overwritten on update.

## Update

```bash
pip install --upgrade newb
scitex-dev skills export          # If using the umbrella export pipeline
```

## Layout

| File | Purpose |
|---|---|
| `SKILL.md`               | Thin index + tagline + when-to-reach-for-newb table |
| `01_quick-start.md`      | Install + minimal CLI + Python forms + output shape |
| `02_canonical-questions.md` | The four canonical questions + why those four |
| `03_author-tests.md`     | `tests_newb.yaml` schema + double grading semantics |
| `04_isolation-runtimes.md` | docker / apptainer; container = boundary, not SDK |
| `05_source-resolution.md` | Local paths, git URLs, project-root auto-detect |
| `06_when-not-to-use.md`  | Explicit boundaries + determinism caveat |
| `07_ci-integration.md`   | JSON / markdown output, GitHub Actions sample |
| `30_env-vars.md`         | NEWB_-prefixed env vars (auth, image, model, cwd, …) |
