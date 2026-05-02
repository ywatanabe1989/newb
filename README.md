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

<p align="center"><sub>Python 3.10+ · bundles <a href="https://github.com/anthropics/claude-agent-sdk-python"><code>claude-agent-sdk</code></a> (Anthropic, MIT) · newb itself AGPL-3.0-only · auth: <code>NEWB_ANTHROPIC_API_KEY</code> or local <code>~/.claude/</code> OAuth</sub></p>

<!-- scitex-badges:start -->
[![PyPI](https://img.shields.io/pypi/v/newb.svg)](https://pypi.org/project/newb/)
[![Python](https://img.shields.io/pypi/pyversions/newb.svg)](https://pypi.org/project/newb/)
[![Tests](https://github.com/ywatanabe1989/newb/actions/workflows/test.yml/badge.svg)](https://github.com/ywatanabe1989/newb/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/ywatanabe1989/newb/graph/badge.svg)](https://codecov.io/gh/ywatanabe1989/newb)
[![Docs](https://readthedocs.org/projects/newb/badge/?version=latest)](https://newb.readthedocs.io/en/latest/)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
<!-- scitex-badges:end -->

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
HOST                                                      DOCKER CONTAINER (ghcr.io/.../newb-runner)
┌──────────────────────────────────┐                      ┌─────────────────────────────────────────────┐
│   Your package                   │                      │                                             │
│                                  │   docker run --rm    │   claude-agent-sdk (Anthropic, MIT)         │
│   docs (any tree of .md files —  │   --network bridge   │     ClaudeAgentOptions(                     │
│      README, scratch notes,      │   -v <staged>:ro     │       cwd="/work/docs",                     │
│      agent skills, …)            │                      │                                             │
│   tests_newb.yaml (optional)     │ ───────────────────► │       setting_sources=[],   # no host CLAUDE│
│                                  │   -e ANTHROPIC_…     │       allowed_tools=["Read"], # NO Bash/Write│
│                                  │                      │       max_turns=8,                          │
│   ├── shutil.copytree            │                      │     )                                       │
│   │   to /tmp/newb-stage-XXX/    │                      │                                             │
│   │   docs/   (read-only mount)  │   stdout = answer    │   for each canonical question:              │
│   └── 1 prompt per canonical Q   │ ◄─────────────────── │     async for msg in query(prompt, options):│
│       + 1 per tests_newb.yaml    │                      │       collect AssistantMessage text         │
│       entry                      │                      │     return ResultMessage.result             │
└──────────────────────────────────┘                      └─────────────────────────────────────────────┘
                │
                ▼
        ┌──────────────────────┐
        │   Report             │
        │   what_for           │
        │   problems_solved    │
        │   quick_start        │
        │   when_not_to_use    │
        │   tests[] (pass/fail)│
        │   tests_summary      │
        └──────────────────────┘
```

**Three isolation runtimes** (`--runtime`):

| Value | FS fence | Net fence | Use when |
|---|---|---|---|
| `host` (default — fast) | soft (Read tool reaches host fs in principle) | none | local development, your own repo, no CI |
| `docker` *(diagrammed above)* | **hard** — only `<staged>:ro` mounted | bridged | CI, third-party repo, untrusted source |
| `apptainer` | **hard** — `--no-home --containall` | rootless | HPC where docker isn't allowed |

newb owns the **test schema** (4 canonical questions + `tests_newb.yaml`
+ graders + report rendering). The SDK owns **everything else**: session
lifecycle, transport, message structuring, tool execution.

## Installation

```bash
pip install newb
pip install newb[yaml]    # + tests_newb.yaml support
```

`claude-agent-sdk` (Anthropic, MIT) is pulled in as a dependency.

## 2 Interfaces

<details open>
<summary><strong>CLI</strong></summary>

<br>

```bash
newb verify .                              # current project — docker by default
newb verify ./src/mypkg/_skills/mypkg      # focused docs subdir
newb verify https://github.com/u/r.git     # git URL — shallow-clones
newb verify . --format markdown >> README.md
newb verify . --runtime apptainer          # HPC variant
newb verify . --template cli-tool          # CLI-focused question set

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

For backward compat, `newb <source>` (positional, no subcommand) is
auto-rewritten to `newb verify <source>`. Self-verification example:

```bash
newb verify https://github.com/ywatanabe1989/newb.git \
  > .history/$(date +%F)-self-verification.txt 2>&1
```

</details>

<details>
<summary><strong>Python API</strong></summary>

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
<summary><strong>MCP server</strong></summary>

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

## Isolation runtimes (`--runtime`)

newb 0.9 dropped the `host` runtime — full agentic permissions on the
host are unsafe (agent could `rm -rf` your projects, `pip install` into
your global env). **The container is the boundary, not the SDK
options** — inside, the agent gets full Read+Write+Edit+Bash+Glob+Grep
so it can actually try the package (`pip install -e .`,
`python -c "import pkg"`, `<pkg> --help`, write a small example).

| Value | Where the agent runs | Isolation | Speed |
|---|---|---|---|
| `docker` *(default)* | `ghcr.io/ywatanabe1989/newb-runner`, project bind-mounted at `/work/project` | hard (filesystem + network ns) | ~15-30 s/q after pull |
| `apptainer` | same image via `apptainer run docker://…` (HPC where docker isn't allowed) | hard (rootless, `--no-home --containall`) | ~20-40 s/q |

The staged copy mounted into the container respects the project's
`.gitignore` (via `git ls-files --cached --others --exclude-standard`)
so build artifacts, virtualenvs, agent state, etc. never enter the
agent's view. Image is published from `containers/Dockerfile` via
`.github/workflows/publish-image.yml`. Override with
`NEWB_DOCKER_IMAGE=...`.

## Author tests (`tests_newb.yaml`)

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  expect_contains: ["does not"]
  judge: "Must redirect to an alternative tool, not hallucinate."
```

Each test combines optional substring grading and an optional LLM judge.

## Auth

newb owns its own env namespace and never silently inherits the
upstream `ANTHROPIC_API_KEY`. Two opt-in vars (set whichever you have):

```bash
# Canonical API key — sk-ant-api03-... (production / CI / redistributed use)
export NEWB_ANTHROPIC_API_KEY=sk-ant-api03-...

# OR: Claude Code subscription (Pro / Max) — sk-ant-oat01-...
# Extract from ~/.claude/.credentials.json:
export NEWB_ANTHROPIC_API_KEY_OAUTH=$(jq -r .claudeAiOauth.accessToken ~/.claude/.credentials.json)
```

Whichever is set is forwarded to the container as `ANTHROPIC_API_KEY`
(the SDK inside reads the canonical name). Per
[Anthropic's commercial ToS](https://www.anthropic.com/legal/commercial-terms),
redistributed / CI use should prefer the API-key form.

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
