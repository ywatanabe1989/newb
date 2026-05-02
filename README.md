# newb

<p align="center">
  <a href="https://scitex.ai">
    <img src="docs/assets/images/scitex-logo-blue-cropped.png" alt="SciTeX" width="400">
  </a>
</p>

<p align="center"><b>Test your package through the eyes of a newbie agent — a fresh AI agent reads only your docs and tries to use your package. If it succeeds, your docs work.</b></p>

<p align="center">
  <a href="https://newb.readthedocs.io/">Full Documentation</a> · <code>pip install newb</code>
</p>

<!-- scitex-badges:start -->
<p align="center">
  <a href="https://pypi.org/project/newb/"><img src="https://img.shields.io/pypi/v/newb.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/newb/"><img src="https://img.shields.io/pypi/pyversions/newb.svg" alt="Python"></a>
  <a href="https://github.com/ywatanabe1989/newb/actions/workflows/test.yml"><img src="https://github.com/ywatanabe1989/newb/actions/workflows/test.yml/badge.svg" alt="Tests"></a>
  <a href="https://codecov.io/gh/ywatanabe1989/newb"><img src="https://codecov.io/gh/ywatanabe1989/newb/graph/badge.svg" alt="Coverage"></a>
  <a href="https://newb.readthedocs.io/en/latest/"><img src="https://readthedocs.org/projects/newb/badge/?version=latest" alt="Docs"></a>
  <a href="https://www.gnu.org/licenses/agpl-3.0"><img src="https://img.shields.io/badge/license-AGPL_v3-blue.svg" alt="License: AGPL v3"></a>
</p>
<!-- scitex-badges:end -->

> Python 3.10+ · bundles [`claude-agent-sdk`](https://github.com/anthropics/claude-agent-sdk-python) (Anthropic, MIT) · newb itself AGPL-3.0-only · auth: `NEWB_ANTHROPIC_API_KEY` or local `~/.claude/` OAuth

---

## Problem and Solution

| # | Problem | Solution |
|---|---------|----------|
| 1 | **What a package is for and how it works isn't obvious.** Authors know their own surface; readers don't. | newb asks four canonical questions automatically — *what for*, *problems solved*, *quick start*, *when not to use* — and reports back what a fresh reader actually understood. |
| 2 | **In this era, the first-class reader of a package is an AI agent**, not a human scrolling through README hash-anchors. Docs that read well to humans can still be unusable to agents. | newb tests docs through the actual reader: a fresh `claude-agent-sdk` session with `setting_sources=[]`, `allowed_tools=["Read"]`, `cwd=<staged copy>` — no host CLAUDE.md, no Bash, no Write. |
| 3 | **Learning a new package is hard for users.** No quick start, missing edge cases, undocumented "when not to use" — all silent failures. | A failing newb run names exactly which question the docs couldn't answer, with the agent's own response — surfacing gaps before users hit them. |
| 4 | **Maintaining doc quality across many packages doesn't scale.** Manual review per release, per package, per branch is the bottleneck for ecosystem-wide quality. | One CLI per package; JSON output for CI; runs in isolation (`host` / `docker` / `apptainer`); pluggable graders (substring + LLM judge) via `tests_newb.yaml`. Plug into a CI matrix and quality scales with your portfolio. |

## How it works

```
HOST                                                       DOCKER CONTAINER (ghcr.io/.../newb-runner)
┌──────────────────────────────────┐                       ┌──────────────────────────────────────────────┐
│  Your project root               │                       │  /work/project   (rw bind-mount)             │
│  (auto-detected — dir with       │                       │    ├── README.md, src/, tests/, examples/    │
│   .git / pyproject.toml /        │                       │    ├── _skills/<pkg>/   ← prompt focus       │
│   setup.py / package.json /      │                       │    └── tests_newb.yaml   (optional)          │
│   Cargo.toml / go.mod)           │                       │                                              │
│                                  │   docker run --rm     │  claude-agent-sdk (Anthropic, MIT)           │
│  ├── stage to                    │   --network bridge    │    ClaudeAgentOptions(                       │
│  │   /tmp/newb-stage-XXX/        │   -v <staged>:rw      │      cwd="/work/project",                    │
│  │   project/   (rw — agent      │   -e ANTHROPIC_API…   │      allowed_tools=["Read","Write","Edit",   │
│  │   needs to pip install)       │   -e NEWB_MODEL       │                     "Bash","Glob","Grep"],   │
│  │                               │   -e NEWB_SKILLS_PATH │      permission_mode="acceptEdits",          │
│  ├── filter via                  │ ────────────────────► │      setting_sources=[],   # no host CLAUDE  │
│  │   `git ls-files --cached      │                       │      max_turns=15,                           │
│  │     --others                  │                       │    )                                         │
│  │     --exclude-standard`       │                       │                                              │
│  │   (or hardcoded ignore        │   stdout = answer     │  agent can ACTUALLY try the package:         │
│  │   list for non-git dirs;      │ ◄──────────────────── │    pip install -e .                          │
│  │   broken symlinks dropped)    │                       │    python -c "import <pkg>"                  │
│  │                               │                       │    <pkg> --help                              │
│  └── one prompt per question     │                       │    write a small example, run a test         │
│      from the chosen template    │                       │  Returns ResultMessage.result per query.     │
│      + one per tests_newb.yaml   │                       │                                              │
│      (questions sent in fresh    │                       │                                              │
│       sessions — no shared       │                       │                                              │
│       conversation state)        │                       │                                              │
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

Three layers, one responsibility each: **container = isolation, SDK
options = agent behavior, agent = exploration.** newb owns the **test
schema** (canonical questions + `tests_newb.yaml` + graders + report
rendering); the SDK owns **everything else**: session lifecycle,
transport, message structuring, tool execution. Runtime details and
backend comparison live in [Isolation runtimes](#isolation-runtimes--runtime) below.

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
newb --help-recursive                      # flatten help across subcommands
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
<summary><strong>Python API ⭐⭐</strong> &nbsp;<sub>callable + run() + self_explain()</sub></summary>

<br>

```python
import newb
report = newb(".")                                       # bare-module callable
print(newb.render_markdown(report))

# Equivalent explicit forms (mirror pytest.main):
report = newb.run(".", template="cli-tool", runtime="docker")
report = newb.self_explain(".")                          # deprecated alias

# Discover what newb can ask:
from newb.question_templates import TEMPLATES, get_template
print(list(TEMPLATES))                                   # ['python-package', 'cli-tool']
print(get_template("python-package").keys())             # the 6 question ids
```

</details>

<details>
<summary><strong>MCP server ⭐⭐</strong> &nbsp;<sub>7 FastMCP tools</sub></summary>

<br>

newb ships a FastMCP server with 7 tools (`newb_verify`, `newb_run`,
`newb_self_explain`, `newb_render_markdown`, `newb_templates_list`,
`newb_templates_show`, `newb_skills_list`, `newb_skills_get`). Install
the optional extra and start over stdio:

```bash
pip install newb[mcp]
newb mcp start
newb mcp list-tools             # introspect
```

For Claude Code or another MCP host, point it at `newb mcp start`.

</details>

<details>
<summary><strong>Skills ⭐⭐</strong> &nbsp;<sub>9 agent-facing leaves under <code>_skills/newb/</code></sub></summary>

<br>

newb ships an agent-facing skill tree with the canonical SciTeX layout:
SKILL.md (thin index) + numbered `NN_topic.md` sub-skills covering
quick-start, the 4 canonical questions, author tests, isolation
runtimes, source resolution, when-not-to-use, CI integration, and env
vars. Browse from the CLI:

```bash
newb skills list
newb skills get SKILL.md
newb skills get 04_isolation        # partial-name match
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
+ `permission_mode="acceptEdits"` + `max_turns=15` so it can actually
try the package (`pip install -e .`, `python -c "import pkg"`,
`<pkg> --help`, write a small example).

| Value | Where the agent runs | Isolation | Speed |
|---|---|---|---|
| `docker` *(default)* | `ghcr.io/ywatanabe1989/newb-runner`, project bind-mounted at `/work/project` | hard (filesystem + network ns) | ~15-30 s/q after pull |
| `apptainer` | same image via `apptainer run docker://…` (HPC where docker isn't allowed) | hard (rootless, `--no-home --containall`) | ~20-40 s/q |

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
`tests[]` array + `tests_summary` (and a back-compat `red_tests`
alias).

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

## Part of SciTeX

`newb` is part of [**SciTeX**](https://scitex.ai). It is the
docs-quality verifier for the ecosystem — every `scitex-*` package's
docs can be re-run through `newb` in CI to catch doc drift before
users do.

>Four Freedoms for Research
>
>0. The freedom to **run** your research anywhere — your machine, your terms.
>1. The freedom to **study** how every step works — from raw data to final manuscript.
>2. The freedom to **redistribute** your workflows, not just your papers.
>3. The freedom to **modify** any module and share improvements with the community.
>
>AGPL-3.0 — because we believe research infrastructure deserves the same freedoms as the software it runs on.

---

<p align="center">
  <a href="https://scitex.ai" target="_blank"><img src="docs/assets/images/scitex-icon-navy-inverted.png" alt="SciTeX" width="40"/></a>
</p>
