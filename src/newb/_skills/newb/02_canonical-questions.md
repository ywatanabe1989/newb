---
name: newb-canonical-questions
description: The four canonical questions newb always asks (what for, problems solved, quick start, when not to use), why these four, and the prompt shape — Read tool only, 1-3 reads expected, max 8 turns.
tags: [newb, scitex-package]
---

# The 4 canonical questions

Every `newb` run asks the agent the same four questions, in this order.
Each question is sent in its own fresh `claude_agent_sdk.query` call —
**no shared conversation state**, so questions cannot influence each
other.

| Key | Prompt summary | Expected shape |
|---|---|---|
| `what_for` | "Read every .md, then in ONE sentence: what is this package for?" | Single declarative sentence. |
| `problems_solved` | "List 3-5 problems this package solves, as a markdown `\| # \| Problem \| Solution \|` table." | Markdown table only, no prose. |
| `quick_start` | "Show the minimal working example as a Python code block." | Just a fenced code block. |
| `when_not_to_use` | "When should someone NOT use this package? If the skills don't say, answer 'not specified in the skills'." | 1-2 sentences OR the explicit fallback. |

## Why these four

A reader who can answer all four can use the package. A reader who
can't is missing one of:

- **purpose** — `what_for` failures mean the README starts in the
  middle, not at the framing
- **value** — `problems_solved` failures mean there's no problem ↔
  solution mapping (just feature lists)
- **try-it-now** — `quick_start` failures mean no minimal example
  reachable from the docs
- **boundaries** — `when_not_to_use` failures mean the docs only sell
  the package, not also describe its limits

The fourth is the most common gap: most packages don't tell the reader
when they shouldn't reach for it. A `not specified in the skills` reply
is itself a useful signal.

## Prompt shape

The actual prompt template lives in `_verify._PROMPTS_DEFAULT`. Each
template:

- Tells the agent to use the `Read` tool to open every `.md` under the
  staged path (the agent's cwd)
- Asks one question, one paragraph
- Constrains the output format (one sentence / markdown table / code
  block / 1-2 sentences)

The SDK is configured with `max_turns=8` — answering should take 1-3
reads. Higher turn counts indicate the docs are scattered enough that
the agent needs to chain reads.

## Tunables (in code, not on the CLI)

| Param | Default | Effect |
|---|---|---|
| `runs_per_prompt` | 1 | If >1, each prompt is asked N times and the value becomes a `list[str]`. Useful for measuring run-to-run drift. |
| `model` | `claude-haiku-4-5` | Pass any Claude model id. The judge step uses the same model. |
