# newb

<p align="center">
  <a href="https://scitex.ai">
    <img src="docs/assets/images/scitex-logo-blue-cropped.png" alt="SciTeX" width="400">
  </a>
</p>

<p align="center"><b>Test your package through the eyes of a newbie agent — because that's who's reading your docs now.</b></p>

<p align="center">
  <a href="https://newb.readthedocs.io/">Full Documentation</a> · <code>pip install newb</code>
</p>

<!-- scitex-badges:start -->
<p align="center">
  <a href="https://pypi.org/project/newb/"><img src="https://img.shields.io/pypi/v/newb.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/newb/"><img src="https://img.shields.io/pypi/pyversions/newb.svg" alt="Python"></a>
  <a href="https://github.com/ywatanabe1989/newb/actions/workflows/test.yml"><img src="https://github.com/ywatanabe1989/newb/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/ywatanabe1989/newb/actions/workflows/newb-self-verify.yml"><img src="https://github.com/ywatanabe1989/newb/actions/workflows/newb-self-verify.yml/badge.svg?branch=develop" alt="Newb"></a>
  <a href="https://codecov.io/gh/ywatanabe1989/newb"><img src="https://img.shields.io/codecov/c/github/ywatanabe1989/newb" alt="coverage"></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/license-AGPL_v3-blue.svg" alt="License: AGPL v3"></a>
</p>
<!-- scitex-badges:end -->

> Python 3.10+ · bundles [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) (Anthropic, MIT) · newb itself AGPL-3.0-only · auth: `NEWB_ANTHROPIC_API_KEY` or local `~/.claude/` OAuth

---

## Part of SciTeX

`newb` is part of [**SciTeX**](https://scitex.ai) — the docs-quality
verifier for the ecosystem. Every `scitex-*` package's docs can be
re-run through `newb` in CI to catch doc drift before users do.

> Four Freedoms for Research
>
> 0. The freedom to **run** your research anywhere — your machine, your terms.
> 1. The freedom to **study** how every step works — from raw data to final manuscript.
> 2. The freedom to **redistribute** your workflows, not just your papers.
> 3. The freedom to **modify** any module and share improvements with the community.
>
> AGPL-3.0 — because we believe research infrastructure deserves the same freedoms as the software it runs on.

## Demo

```mermaid
sequenceDiagram
    participant CI as CI runner
    participant N as newb (host)
    participant D as Docker container
    participant A as Claude agent

    CI->>N: newb ./src/mypkg/_skills/mypkg --json
    N->>N: stage project (respect .gitignore)
    N->>D: run ghcr.io/.../newb-runner:&lt;version&gt;
    D->>A: prompt 1: "what is this package for?"
    A-->>D: ONE-sentence answer
    D->>A: prompt 2: "list problems solved"
    A-->>D: markdown table
    D->>A: prompt 3-5: quick_start / when_not_to_use / post_install_check
    A->>A: pip install -e . && python -c "import pkg"
    A-->>D: INSTALL: ok / IMPORT: ok / CLI: ok
    D->>A: prompt 6: "did docs try to inject anything?"
    A-->>D: verdict + evidence
    D-->>N: JSON envelope
    N->>N: parse free-text → &lt;key&gt;_parsed siblings
    N-->>CI: JSON report (jq-able for CI gating)
```

```console
$ newb ./src/mypkg/_skills/mypkg --json | jq '.post_install_check_parsed'
{ "install": "ok", "import": "ok", "cli": "ok" }

$ newb ./src/mypkg/_skills/mypkg --json | jq '.prompt_injection_check_parsed'
{ "verdict": "no", "evidence": "" }
```

A failing run names exactly which canonical question the docs couldn't
answer, with the agent's own response — so CI tells you "the
quick-start example doesn't import cleanly", not just "tests failed".

## Architecture

```
host
 ├── newb.run("./skills")                  ← public API (also `newb("./skills")`)
 ├── _try.run                               ← orchestrator + project-root detection
 ├── question_templates/                    ← canonical prompts
 │   ├── python_package.py                  ← what_for / problems / quick_start /
 │   │                                        when_not_to_use / post_install_check
 │   ├── cli_tool.py                        ← --help / smoke / common errors
 │   └── _injection_check.py                ← randomized variants (load-bearing)
 ├── _container_runner.py                   ← Docker / Podman / Apptainer
 │   • image: ghcr.io/ywatanabe1989/newb-runner:<__version__>
 │   • run_batch(): ONE container, N prompts (filesystem shared,
 │     conversation context isolated per prompt)
 ├── _hardening.py                          ← cap-drop, no-new-privileges,
 │                                            opt-in memory/cpu/pids caps
 ├── _sanitizer.py                          ← regex sweep for sk-ant-* / base64 leaks
 └── _parsers.py                            ← free-text → `<key>_parsed` for jq-able CI
```

The container is the **only** isolation boundary; the agent is
unconstrained inside (Read + Write + Edit + Bash + Glob + Grep) so it
can actually `pip install -e . && python -c "import pkg"` to verify.

## Problem and Solution

| # | Problem | Solution |
|---|---|---|
| 1 | **The first-class reader of a modern package is an AI agent**, not a human scrolling through README hash-anchors. Docs that read well to humans can still be unusable to agents — and "unusable to an agent" increasingly means "unusable, period". | newb tests docs through that exact reader. A fresh `claude-agent-sdk` session inside a hardened container, with `setting_sources=[]` (no host CLAUDE.md leaking) and full agentic tools, actually tries to install + import + use the package. The verdict comes from the agent's own success, not heuristic linting. |
| 2 | **Manual review across many packages doesn't scale.** For an ecosystem with N packages × M releases × K branches, "is the README still good?" is a question nobody has time to answer by hand. | One CLI per package, JSON output for CI, container-isolated (`docker` / `podman` / `apptainer`), pluggable graders (substring + LLM judge) via `tests_newb.yaml`. Plug into a CI matrix and doc quality scales with your portfolio. |
| 3 | **Failures are silent.** No quick start, undocumented "when not to use", install steps that work-on-my-machine — all surface only when a real user hits them. | A failing newb run names exactly which canonical question the docs couldn't answer, with the agent's own response. Bonus: `post_install_check` actually runs `pip install` + `import` + `<pkg> --help` inside the container, so install-state breakage shows up before release. |
| 4 | **Untrusted docs are an injection surface.** A docs-reading agent is a textbook indirect-prompt-injection target. | Container is the boundary (`--cap-drop=ALL`, `--network=bridge`, `--rm`), `NEWB_ANTHROPIC_API_KEY`-only auth namespace, `prompt_injection_check` consistency probe in every run, optional `newb[security]` for Protect AI's pre-flight scanner. Full threat model: [`SECURITY.md`](SECURITY.md). |

## How it works

```
HOST                                            CONTAINER
┌────────────────────────┐                      ┌────────────────────────┐
│  Your project root     │  docker run --rm -i  │  /work/project (rw)    │
│  staged → tmp dir      │ ────────────────────►│  claude-agent-sdk      │
│  (respects .gitignore) │  stdin: prompts      │    full agentic tools  │
│                        │ ◄──────────────────  │    setting_sources=[]  │
│  Report (JSON / md)    │  stdout: results     │  → tries the package   │
└────────────────────────┘                      └────────────────────────┘
```

Three layers, one responsibility each: **container = isolation, SDK
options = agent behavior, agent = exploration.** newb owns the **test
schema** (canonical questions + `tests_newb.yaml` + graders + report
rendering); the SDK owns **everything else**: session lifecycle,
transport, message structuring, tool execution.

<details>
<summary><strong>Detailed architecture diagram</strong> — staging, SDK options, batched-prompt envelope</summary>

```
HOST                                                       CONTAINER (ghcr.io/ywatanabe1989/newb-runner:<v>)
┌──────────────────────────────────┐                       ┌──────────────────────────────────────────────┐
│  Your project root               │                       │  /work/project   (rw bind-mount)             │
│  (auto-detected — dir with       │                       │    ├── README.md, src/, tests/, examples/    │
│   .git / pyproject.toml /        │                       │    ├── _skills/<pkg>/   ← prompt focus       │
│   setup.py / package.json /      │                       │    └── tests_newb.yaml   (optional)          │
│   Cargo.toml / go.mod)           │                       │                                              │
│                                  │ docker run --rm -i    │  claude-agent-sdk (Anthropic, MIT)           │
│  ├── stage to                    │   --network bridge    │    ClaudeAgentOptions(                       │
│  │   /tmp/newb-stage-XXX/        │   --cap-drop=ALL      │      cwd="/work/project",                    │
│  │   project/   (rw — agent      │   -v <staged>:rw      │      permission_mode="bypassPermissions",    │
│  │   needs to pip install)       │   -e NEWB_…           │      setting_sources=[],   # no host CLAUDE  │
│  │                               │ ────────────────────► │      max_turns=15,                           │
│  ├── filter via                  │   stdin:              │    )   # --scope docs uses acceptEdits +     │
│  │   `git ls-files --cached      │   {"prompts":[…]}     │        # allowed_tools=["Read","Glob","Grep"]│
│  │     --others                  │                       │                                              │
│  │     --exclude-standard`       │   stdout:             │  agent can ACTUALLY try the package:         │
│  │   (or hardcoded ignore        │   {"results":[…]}     │    pip install -e .                          │
│  │   list for non-git dirs;      │ ◄──────────────────── │    python -c "import <pkg>"                  │
│  │   broken symlinks dropped)    │                       │    <pkg> --help                              │
│  │                               │                       │    write a small example, run a test         │
│  └── ALL prompts batched into    │                       │                                              │
│      ONE container; per-prompt   │                       │  One container per `newb` run. Per-prompt    │
│      independent query() so      │                       │  query() so context never leaks; on-disk     │
│      conversations are isolated, │                       │  state (pip install) DOES persist across     │
│      filesystem state shared     │                       │  prompts within the run.                     │
└──────────────────────────────────┘                       └──────────────────────────────────────────────┘
                │
                ▼
        ┌────────────────────────────────────┐
        │  Report                            │
        │    package, template               │
        │    what_for, problems_solved,      │
        │    quick_start, when_not_to_use,   │
        │    post_install_check,             │
        │    prompt_injection_check          │
        │    tests[] (substring + LLM judge) │
        │    tests_summary                   │
        └────────────────────────────────────┘
```

Runtime details + backend comparison live in [Isolation runtimes](#isolation-runtimes--runtime).

</details>

### Architecture invariants (verified empirically)

A single `newb .` invocation is **one** container holding **N** prompts.
Two properties matter, and both have been smoke-tested end-to-end:

| Property | What it means | Verified? |
|---|---|---|
| **Filesystem state persists across prompts** | A `pip install -e .` (or `touch /tmp/marker`) in prompt *i* is visible to prompt *j>i*. So `post_install_check` actually validates the install for downstream questions. | ✅ — prompt 1 ran `pip install --user six` and wrote a marker file; prompt 2 (independent agent) successfully `import six` and read the marker content back. |
| **Conversation context does NOT leak across prompts** | Each prompt is a fresh `query()` — no message history carried over — so answers can't bias each other. | ✅ — prompt 1 was told a secret word; prompt 2 (asked for it) reported `NO_MEMORY`. |

So "newb agent lives long" only **within** one run (prompt-to-prompt
filesystem sharing). It does NOT live across runs: the container is
`--rm`'d at the end, every `newb` invocation is a cold start. The
optional `--pip-cache` mount carries wheel downloads forward; install
state itself does not.

## Installation

```bash
pip install newb           # core (CLI + Python API)
pip install newb[yaml]     # + custom YAML templates / tests_newb.yaml
pip install newb[mcp]      # + FastMCP server (newb mcp start)
pip install newb[all]      # everything above
```

`claude-agent-sdk` (Anthropic, MIT) is pulled in as a dependency.

<details>
<summary><strong>Auth — NEWB_-prefixed env vars only (no upstream surprises)</strong></summary>

<br>

newb owns its own env namespace and never silently inherits the
upstream `ANTHROPIC_API_KEY`. One opt-in var, opaque to newb:

```bash
# Real Anthropic API key (production / CI / redistributed use)
export NEWB_ANTHROPIC_API_KEY=sk-ant-api03-...

# OR: a Claude Code Pro / Max OAuth access token. Extract from
# ~/.claude/.credentials.json:
export NEWB_ANTHROPIC_API_KEY=$(jq -r .claudeAiOauth.accessToken ~/.claude/.credentials.json)
```

The Anthropic backend accepts both `sk-ant-api*` (API keys) and
`sk-ant-oat*` (Claude Code OAuth access tokens) on the same
Authorization header — newb forwards the value verbatim into the
container, where the bundled CLI promotes it to `ANTHROPIC_API_KEY`.
Per
[Anthropic's commercial ToS](https://www.anthropic.com/legal/commercial-terms),
redistributed / CI use should prefer the API-key form.

</details>

## 4 Interfaces

<details open>
<summary><strong>CLI ⭐⭐⭐</strong> &nbsp;<sub>primary surface</sub></summary>

<br>

```bash
newb .                              # current project — docker by default
newb ./src/mypkg/_skills/mypkg      # focused docs subdir
newb https://github.com/u/r.git     # git URL — shallow-clones
newb . --format markdown >> README.md
newb . --runtime apptainer          # HPC variant
newb . --template cli-tool          # CLI-focused question set

# Introspection
newb templates list                        # built-in question templates
newb templates show python-package
newb skills list                           # newb's own _skills/ leaves
newb skills get SKILL.md
newb list-python-apis                      # public Python surface
newb mcp list-tools                        # FastMCP tools exposed
newb mcp start                             # serve over stdio (for IDEs)
newb show-env-template                     # NEWB_* env-var schema (.src or --json)
newb --help-recursive                      # flatten help across subcommands

# CI integration
newb . --json > report.json
newb gate report.json                      # exit 0/1 vs [tool.newb.gate]

# Maintainer plumbing — `newb dev` group
newb dev install <owner>/<repo>            # set-secret + scaffold-workflow combo
newb dev set-secret <owner>/<repo>         # push NEWB_ANTHROPIC_API_KEY to GH
newb dev scaffold-workflow <owner>/<repo>  # drop .github/workflows/newb.yml

# Shell completion
newb install-shell-completion              # bash / zsh / fish (auto-detected)
newb print-shell-completion bash           # emit script to stdout
newb skills install                        # copy skill leaves into ~/.claude/skills/
```

pytest-style: `newb <target>` is the canonical invocation — no verb in
front. Subcommands (`templates`, `skills`, `mcp`, `list-python-apis`)
are introspection-only.

Self-verification example:

```bash
newb https://github.com/ywatanabe1989/newb.git \
  > .history/$(date +%F)-self-verification.txt 2>&1
```

</details>

<details>
<summary><strong>Python API ⭐⭐</strong> &nbsp;<sub>callable + run()</sub></summary>

<br>

```python
import newb
report = newb(".")                                       # bare-module callable
print(newb.render_markdown(report))

# Equivalent explicit form (mirrors pytest.main):
report = newb.run(".", template="cli-tool", runtime="docker")

# Discover what newb can ask:
from newb.question_templates import TEMPLATES, get_template
print(list(TEMPLATES))                                   # ['python-package', 'cli-tool']
print(get_template("python-package").keys())             # the 6 question ids
```

</details>

<details>
<summary><strong>MCP server ⭐⭐</strong> &nbsp;<sub>7 FastMCP tools</sub></summary>

<br>

newb ships a FastMCP server with these tools (`newb_verify`, `newb_run`,
`newb_render_markdown`, `newb_templates_list`, `newb_templates_show`,
`newb_skills_list`, `newb_skills_get`). Install the optional extra and
start over stdio:

```bash
pip install newb[mcp]
newb mcp start
newb mcp list-tools             # introspect
```

For Claude Code or another MCP host, point it at `newb mcp start`.

</details>

<details>
<summary><strong>Skills ⭐⭐</strong> &nbsp;<sub>14 agent-facing leaves under <code>_skills/newb/</code></sub></summary>

<br>

newb ships an agent-facing skill tree with the canonical SciTeX layout:
SKILL.md (thin index) + numbered `NN_topic.md` sub-skills covering
installation, quick-start, Python API, CLI reference, MCP tools, the
6 canonical questions, author tests, isolation runtimes, source
resolution, when-not-to-use, CI integration, CI badge adoption, and
env vars. Browse from the CLI:

```bash
newb skills list
newb skills get SKILL.md
newb skills get 12_isolation        # partial-name match
newb skills install                 # copy leaves into ~/.claude/skills/newb/
```

Source: [`src/newb/_skills/newb/`](src/newb/_skills/newb/).

</details>

## Isolation runtimes (`--runtime`)

<details>
<summary><strong>docker / apptainer — what each fences off, when to use which</strong></summary>

<br>

newb 0.9 dropped the `host` runtime — full agentic permissions on the
host are unsafe (agent could `rm -rf` your projects, `pip install` into
your global env). **The container is the boundary, not the SDK
options** — inside, the agent gets full `Read+Write+Edit+Bash+Glob+Grep`
+ `permission_mode="bypassPermissions"` (for `--scope all`, the
default) + `max_turns=15` so it can actually try the package
(`pip install -e .`, `python -c "import pkg"`, `<pkg> --help`, write
a small example). `--scope docs` switches to `acceptEdits` +
`allowed_tools=["Read","Glob","Grep"]` for read-only audits.

Since 0.19.0 all prompts in a run share **one** container — per-prompt
`query()` keeps conversations isolated, but on-disk state
(`pip install -e .` from `post_install_check`) persists across
prompts within the run.

| Value | Where the agent runs | Isolation |
|---|---|---|
| `docker` *(default)* | `ghcr.io/ywatanabe1989/newb-runner`, project bind-mounted at `/work/project` | hard (filesystem + network ns) |
| `podman` | same image, rootless, no daemon | hard (filesystem + network ns) |
| `apptainer` | same image via `apptainer run docker://…` (HPC where docker isn't allowed) | hard (rootless, `--no-home --containall`) |

The staged copy mounted into the container respects the project's
`.gitignore` so build artifacts, virtualenvs, agent state, etc. never
enter the agent's view. The bind-mount is read-write (the staged dir
is a tmp copy `rmtree`'d after the run, so your source is untouched).
Image is published from `containers/Dockerfile` via
`.github/workflows/publish-image.yml`. Override with
`NEWB_DOCKER_IMAGE=...`.

</details>

## Question templates — what newb asks the agent

newb runs **a set of prompts** (a *template*) against your project.
Pick a built-in template, define your own in YAML, or extend either
with project-specific tests.

<details open>
<summary><strong>Built-in templates</strong></summary>

<br>

| `--template` value | Question keys | Best for |
|---|---|---|
| `python-package` *(default)* | `what_for`, `problems_solved`, `quick_start`, `when_not_to_use`, `post_install_check`, `prompt_injection_check` | Any pip-installable Python project |
| `cli-tool` | `what_for`, `install_and_help`, `subcommand_tree`, `typical_usage`, `common_pitfall`, `prompt_injection_check` | Packages whose primary value is a CLI |

Both templates exercise the new full-perms container — the agent
actually runs `pip install -e .` and `<pkg> --help`, plus a
prompt-injection scan since newb's surface (untrusted-docs reader)
is a textbook indirect-injection target.

```bash
newb .                              # default: python-package
newb . --template cli-tool
newb templates list                        # discover what's available
newb templates show python-package         # see the actual prompts
```

</details>

<details>
<summary><strong>Project-specific extras (<code>tests_newb.yaml</code>)</strong></summary>

<br>

Drop a `tests_newb.yaml` next to your docs; each entry becomes an
extra question with author-defined grading layered on top of the
chosen template:

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  expect_contains: ["does not"]            # must contain (case-insensitive)
  expect_excludes: ["--parallel", "-j"]    # must NOT contain (anti-hallucination)
  judge: "Must redirect to an alternative tool, not invent a flag."
```

Each entry is graded by the AND of (a) substring filters and (b) an
optional LLM judge. The grading detail lands in the report's
`tests[]` array and `tests_summary`.

</details>

<details>
<summary><strong>Custom templates (your own YAML)</strong></summary>

<br>

For a different *prompt set* (not just extras), define a YAML template
and pass its path to `--template`:

```bash
newb . --template ./my-template.yaml
```

```yaml
# my-template.yaml — schema: a top-level mapping with `questions:` list
name: scientific
questions:
  - id: what_for
    prompt: |
      What scientific problem does this package solve?
      Answer in 1-2 sentences.
  - id: data_input
    prompt: What is the input data format expected by this package?
  - id: validity_check
    prompt: How can a user verify the output is correct?
```

YAML support requires `pip install newb[yaml]`. Future built-in
templates planned: `api-sdk`, `scientific`, `web-app`, `ml-model`.

</details>

## Security

newb runs an AI agent against arbitrary package documentation —
that's a real attack surface. The container is the boundary
(`--cap-drop=ALL`, `--network=bridge`, `--rm`), the agent runs
with `setting_sources=[]` so host `~/.claude/CLAUDE.md` never
reaches it, and `NEWB_ANTHROPIC_API_KEY` is the single opt-in
auth namespace. Prompt injection at the model level is unsolved
— treat verdicts on adversarial packages as heuristic.

Full threat model + operating recommendations: [`SECURITY.md`](SECURITY.md)
· [`docs/security/threat-model.md`](docs/security/threat-model.md).

---

<p align="center">
  <a href="https://scitex.ai" target="_blank"><img src="docs/assets/images/scitex-icon-navy-inverted.png" alt="SciTeX" width="40"/></a>
</p>
