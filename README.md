# newb

<p align="center"><img src="./assets/newb-logo.png" width="220" alt="newb mascot"/></p>

A fresh AI agent reads only your docs and tries to use your package. If it
succeeds, your docs work.

## How it works

```
┌──────────────────────┐    ┌────────────────────────────────────┐    ┌──────────────────────┐
│   Your package       │    │   claude-agent-sdk                 │    │   Report             │
│                      │    │   (Anthropic, official)            │    │                      │
│   ./docs/   or       │    │                                    │    │   what_for           │
│   ./_skills/<pkg>/   │ →  │   fresh Claude Code session,       │ →  │   problems_solved    │
│   tests_newb.yaml    │    │   setting_sources=[],              │    │   quick_start        │
│   (optional)         │    │   allowed_tools=["Read"]           │    │   when_not_to_use    │
│                      │    │   cwd=<staged copy of your docs>   │    │   tests[] (pass/fail)│
└──────────────────────┘    └────────────────────────────────────┘    └──────────────────────┘
            │                              ▲
            │                              │  newb sends N prompts via the SDK's
            └────── stages copy ───────────┘  ``query()`` async iterator
                                              (structured streaming, no --print)
```

newb owns the **test schema** (4 canonical questions + `tests_newb.yaml`
+ graders + report rendering). The SDK owns **everything else**: session
lifecycle, transport, message structuring, tool execution. No docker, no
multiplexer, no wire format — just a Python import.

## Install

```bash
pip install newb
```

`claude-agent-sdk` (Anthropic, MIT) is pulled in as a dependency.

## Use

```bash
newb ./docs                                # any dir of .md files
newb ./src/mypkg/_skills/mypkg             # standard SciTeX layout
newb https://github.com/user/repo.git      # git URL — shallow-clones
newb ./docs --format markdown >> README.md
```

Asks a fresh Claude agent four canonical questions (what for / problems
solved / quick start / when not to use), plus any author-defined tests
in `tests_newb.yaml`. Output: JSON (for CI) or markdown.

### Author tests (`tests_newb.yaml`)

```yaml
- name: redirects_parallel
  prompt: How do I run things in parallel?
  expect_contains: ["does not"]
  judge: "Must redirect to an alternative tool, not hallucinate."
```

Each test combines optional substring grading and an optional LLM judge.

## Auth

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...     # canonical, ToS-clean
```

Per [Anthropic's commercial ToS](https://www.anthropic.com/legal/commercial-terms),
products built on the Claude Agent SDK should use API key auth. On a
personal machine where you've run `claude` to authenticate, an existing
`~/.claude/` OAuth login also works (the SDK's bundled CLI inherits it),
but Anthropic doesn't sanction this for redistributed products.

## Isolation

`setting_sources=[]` skips your host `CLAUDE.md` / `.claude/` settings.
`allowed_tools=["Read"]` limits the agent to file reads. `cwd` is set to
a tmp copy of your skills dir, so the agent's filesystem horizon is the
package's own content. No Bash, no Write, no WebFetch.

## Library

```python
import newb
report = newb("./docs")
print(newb.render_markdown(report))
```

## Requirements

- Python 3.10+
- `claude-agent-sdk` (auto-installed; bundles a Claude CLI)
- `$ANTHROPIC_API_KEY` (or local `claude` login)

## License

newb itself: AGPL-3.0-only.
The bundled `claude-agent-sdk`: MIT, governed by
[Anthropic's Commercial Terms of Service](https://www.anthropic.com/legal/commercial-terms).
