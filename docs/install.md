# Installing newb CI into a repo

`newb install` drops the `Newb | passing` workflow into a target
GitHub repo and sets the one secret it needs. Use it to onboard a
single repo; for multi-repo loops, write a shell loop or use a
domain-specific tool that calls `newb install` per repo.

## One-shot

```bash
export NEWB_ANTHROPIC_API_KEY="sk-ant-..."

newb install <owner>/<repo>          # opens a PR adding .github/workflows/newb.yml
newb install <owner>/<repo> --push   # direct-push to default branch
newb install                         # current directory's git remote
newb install .                       # explicit current remote
```

The combined verb runs:

1. `newb set-secret` — sets `NEWB_ANTHROPIC_API_KEY` on the repo
   (reads the value from your local env).
2. `newb scaffold-workflow` — writes `.github/workflows/newb.yml`,
   either via PR (default) or direct-push.

Both verbs are idempotent — re-running skips already-set secrets and
existing workflow files. Pass `--force` to overwrite.

## Individual verbs

```bash
newb scaffold-workflow <owner>/<repo>           # PR-only
newb scaffold-workflow <owner>/<repo> --push    # direct-push
newb set-secret <owner>/<repo>                  # secret only
```

`--no-secret` on `newb install` skips step 1 (e.g. when an org-level
secret is already in scope).

## Prerequisites

- `gh` CLI authenticated (`gh auth status` is green) with `repo` and
  `workflow` scopes. Required for both verbs.
- `NEWB_ANTHROPIC_API_KEY` exported in your shell when running
  `set-secret` / `install` without `--no-secret`.
- The target repo exists and you have push (or PR) access.

## After install

1. **Trigger once manually** from the target repo's Actions tab
   (`workflow_dispatch`). Read the `newb-report.json` artifact.
2. Fix anything the agent couldn't figure out (usually: missing
   quick-start in docs, or `pip install -e .` failing — chmod
   handling on the bind-mounted tree is built into the runner).
3. **Add the badge** to the README — markdown one-liner in
   [`docs/badge.md`](badge.md).
4. (Optional) **Hard-gate** the workflow by uncommenting the
   `newb gate` step in the generated workflow file.

## Multi-repo loops

`newb` itself is a single-repo tool by design — it knows nothing
about ecosystems or registries. To roll out across many repos, drive
it from a shell loop:

```bash
for repo in owner/pkg1 owner/pkg2 owner/pkg3; do
  newb install "$repo"
done
```

Or wrap it in a domain-specific tool that owns the repo list (e.g. a
package-ecosystem manager that calls `newb install` per package).

## Troubleshooting

- **`gh: not found`** — install `gh` from https://cli.github.com/.
- **`gh auth status` fails** — `gh auth login` first.
- **`newb: NEWB_ANTHROPIC_API_KEY env var is empty`** — export the
  key before running, or use `--no-secret` if your org has one set.
- **Auth error on `docker pull`** during the workflow run — shouldn't
  happen, the runner image is public. If it does, GitHub may have
  flipped the package back to private; check the package's settings
  page.
- **`INSTALL: fail`** in the report — usually a real install bug in
  the package or an environment issue. Read the EVIDENCE block.
- **`prompt_injection_check.found == true`** — the agent flagged
  something. Read EVIDENCE; if it's a false positive, file an issue
  on newb.
