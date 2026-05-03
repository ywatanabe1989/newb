"""Parse the canonical-question replies into structured fields.

The agent emits free-text replies in formats newb explicitly prompts
for (e.g. ``INSTALL: ok / IMPORT: ok / CLI: ok``). Free text is good
for humans reading the markdown report; for CI gating it's fragile —
``Install:`` vs ``INSTALL:`` would defeat a substring grep. These
parsers extract a structured form alongside the prose so CI can do::

    jq -e '.post_install_check_parsed.install == "ok"' newb.json

instead of fragile string matching against the raw reply.

Design choices:

- **Host-side regex, not agent-side JSON.** Asking the LLM to emit
  JSON adds an output-format constraint we'd have to police forever.
  Trusting it to follow a simple textual format we explicitly prompt
  for is more deterministic. We own the parser, so the format is
  ours to evolve.
- **``"unknown"`` sentinel** when the agent doesn't follow the
  prompted format, instead of raising. Off-script replies are
  themselves useful CI signals (``unknown`` !=  ``ok``).
- **Case-insensitive, whitespace-tolerant.** ``INSTALL: ok``,
  ``install: OK``, ``Install :  ok`` all parse identically.
- **Additive** — parsers don't mutate the original free-text reply;
  ``<key>`` (prose) and ``<key>_parsed`` (dict) coexist in the
  report.
"""

from __future__ import annotations

import json
import re
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Structured-emission preference
# ---------------------------------------------------------------------------
#
# Newb prompts the agent to append a fenced ```newb-json block at the end
# of structured replies (post_install_check, install_and_help,
# prompt_injection_check). This is a stepping-stone toward true Anthropic
# Tool Use: the agent's structured answer arrives as parseable JSON we own,
# instead of free-text we have to regex-mine. When the block is present and
# parses, parsers below trust it over the regex path. Missing or malformed
# blocks fall back to the regex parser, so older agent replies still work.

_NEWB_JSON_BLOCK = re.compile(
    r"```newb-json\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_newb_json(text: str) -> Optional[Dict[str, object]]:
    """Return the LAST ```newb-json block parsed as a dict, or None."""
    if not text:
        return None
    matches = _NEWB_JSON_BLOCK.findall(text)
    for raw in reversed(matches):
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj
    return None


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------


# Matches `<LABEL>:<whitespace><VALUE>` on its own line, label and value
# both case-insensitive. Anchored to start-of-line (with optional leading
# whitespace / markdown bullet) so the first occurrence wins, ignoring
# any later restatements in EVIDENCE blocks.
def _line_field(label: str, text: str) -> Optional[str]:
    """Return the first whitespace-stripped value after ``<label>:``,
    or ``None`` if the label doesn't appear."""
    pattern = (
        r"^[ \t>*\-]*"  # leading bullet/whitespace tolerated
        r"\**\s*"  # optional bold markers around label
        rf"{re.escape(label)}"
        r"\**"  # optional close-bold
        r"\s*:\s*"  # the colon + spaces
        r"\**"  # optional bold around value
        r"([^\n*]+?)"  # the value (non-greedy, no newlines/asterisks)
        r"\**"  # optional close-bold
        r"\s*$"  # end-of-line
    )
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def _ok_fail_na(raw: Optional[str]) -> str:
    """Normalize ``ok`` / ``fail`` / ``n/a`` (anything else → ``unknown``)."""
    if raw is None:
        return "unknown"
    s = raw.strip().lower()
    # Strip trailing punctuation / parens that LLMs sometimes add.
    s = re.sub(r"[.\s)(\]\[]+$", "", s).strip()
    if s.startswith("ok"):
        return "ok"
    if s.startswith("fail"):
        return "fail"
    if s in {"n/a", "na", "not applicable", "skip", "skipped"}:
        return "n/a"
    return "unknown"


def _yes_no(raw: Optional[str]) -> str:
    if raw is None:
        return "unknown"
    s = raw.strip().lower()
    s = re.sub(r"[.\s)(\]\[]+$", "", s).strip()
    if s.startswith(("yes", "true", "found")):
        return "yes"
    if s.startswith(("no", "false", "none", "clean")):
        return "no"
    return "unknown"


# ---------------------------------------------------------------------------
# Per-question parsers
# ---------------------------------------------------------------------------


def parse_post_install_check(text: str) -> Dict[str, str]:
    """Parse the ``post_install_check`` reply.

    Expected shape (prompted by newb)::

        INSTALL: <ok|fail>
        IMPORT: <ok|fail>
        CLI: <ok|fail|n/a>
        EVIDENCE:
          <one-line summary or first error line>

    Returns a dict with keys ``install``, ``import``, ``cli`` —
    each one of ``ok``, ``fail``, ``n/a``, or ``unknown``. A trailing
    ```newb-json block, if present and parseable, takes precedence over
    the regex path for the keys it carries.
    """
    out = {
        "install": _ok_fail_na(_line_field("INSTALL", text)),
        "import": _ok_fail_na(_line_field("IMPORT", text)),
        "cli": _ok_fail_na(_line_field("CLI", text)),
    }
    blob = _extract_newb_json(text)
    if blob is not None:
        for k in ("install", "import", "cli"):
            if k in blob:
                out[k] = _ok_fail_na(str(blob[k]))
    return out


def parse_install_and_help(text: str) -> Dict[str, str]:
    """Parse the ``install_and_help`` reply (cli-tool template).

    Expected shape::

        INSTALL: <ok|fail>
        HELP: <ok|fail>
        EVIDENCE:
          <…>
    """
    out = {
        "install": _ok_fail_na(_line_field("INSTALL", text)),
        "help": _ok_fail_na(_line_field("HELP", text)),
    }
    blob = _extract_newb_json(text)
    if blob is not None:
        for k in ("install", "help"):
            if k in blob:
                out[k] = _ok_fail_na(str(blob[k]))
    return out


def parse_prompt_injection_check(text: str) -> Dict[str, object]:
    """Parse the ``prompt_injection_check`` reply.

    Expected shape::

        FOUND: <yes|no>
        EVIDENCE:
          <…>

    Returns ``{"found": True|False, "found_raw": "yes|no|unknown"}``.
    The boolean form is what jq users want; the raw form preserves
    the ``unknown`` sentinel so callers can detect off-script replies.
    """
    raw = _yes_no(_line_field("FOUND", text))
    blob = _extract_newb_json(text)
    if blob is not None and "found" in blob:
        v = blob["found"]
        if isinstance(v, bool):
            raw = "yes" if v else "no"
        elif isinstance(v, str):
            raw = _yes_no(v)
    return {
        "found": True if raw == "yes" else (False if raw == "no" else None),
        "found_raw": raw,
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

# Question-key → parser. Adding a parser for a new question key is the
# only place the report shape grows.
_PARSERS = {
    "post_install_check": parse_post_install_check,
    "install_and_help": parse_install_and_help,
    "prompt_injection_check": parse_prompt_injection_check,
}


def attach_parsed_fields(report: Dict[str, object]) -> Dict[str, object]:
    """Add ``<key>_parsed`` siblings to recognized question keys.

    Mutates and returns ``report``. Free-text replies stay untouched;
    parsed siblings are additive. ``runs_per_prompt > 1`` produces a
    list of replies, in which case we parse each and emit a list of
    parsed dicts (preserving alignment).
    """
    for key, parser in _PARSERS.items():
        value = report.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            report[f"{key}_parsed"] = [
                parser(v if isinstance(v, str) else "") for v in value
            ]
        elif isinstance(value, str):
            report[f"{key}_parsed"] = parser(value)
    return report


# EOF
