---
name: newb-source-resolution
description: How newb resolves a SOURCE argument — local paths pass through; git URLs are shallow-cloned; the inside-clone search order is _skills/ → docs/ → repo root, picking the first dir that contains any .md file.
tags: [newb]
---

# Source resolution

`newb <SOURCE>` accepts:

| Form | Treatment |
|---|---|
| `./docs` (local dir) | Used as-is. |
| `./src/<pkg>/_skills/<pkg>` (local dir) | Used as-is. |
| `https://github.com/u/r.git` / `git@…` / anything `*.git` | Shallow-cloned (`git clone --depth=1`) into a tmp dir. |

Detection of "URL-ness" (`_try._is_url`):

```python
spec.startswith(("http://", "https://", "git@")) or spec.endswith(".git")
```

## Inside the cloned repo: search order

After a successful clone, `newb` looks for the first directory that
contains any `.md`:

1. `<repo>/_skills`
2. `<repo>/docs`
3. `<repo>` (the repo root itself)

If all three are empty of markdown the run aborts with
`FileNotFoundError`.

## Validation rules (local + remote)

`_validate_source`:

- Path must resolve and be a directory (`Path.expanduser().resolve()`).
- Must recursively contain at least one `.md` file
  (`any(p.rglob("*.md"))`).

Failures raise `FileNotFoundError` before any agent call (no API spend
on broken inputs).

## Cleanup

- A shallow clone's tmp dir is `shutil.rmtree`'d after the run, even
  when the agent call raises.
- Each runner also stages its own copy under `<tmp>/<name>/` (so the
  agent's cwd is bounded to the package's content) and cleans up via
  `runner.close()` in the same `finally` block.

## Skill-tree convention

A canonical layout the agent works well against:

```
src/<pkg>/
  _skills/
    <pkg>/             ← `newb src/<pkg>/_skills/<pkg>`
      SKILL.md         ← thin index
      01_<topic>.md
      02_<topic>.md
      ...
```

newb's own skills follow this layout — see
[../newb/](../newb/) (you are reading it now).
