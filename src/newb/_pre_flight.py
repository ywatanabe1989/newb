# ---
# Timestamp: 2026-05-02
# Author: ywatanabe
# File: src/newb/_pre_flight.py
# ---

"""Pre-flight prompt-injection scanner (Phase 1.5).

Runs on the staged project directory *before* the container starts and the
agent reads anything. Pure regex, no LLM dependency, no network. Catches
the obvious cases; sophisticated attacks fall through to the in-template
prompt_injection_check question and (in 0.12.0+) the LLM-based scanners.

Scanned files:
- *.md, *.txt anywhere under the staged dir
- tests_newb.yaml / tests_newb.yml — the `prompt:` fields are author-supplied
  half-trusted input that goes directly to the agent

NOT scanned:
- Source code (.py etc.) — the agent reads source for legitimate exploration;
  scanning here would generate massive false positives on technical terms.
  Trade-off accepted: an attacker who hides injection inside a Python
  docstring can bypass the pre-flight. The in-template self-check and the
  output sanitizer are the next layers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Finding:
    path: str
    """Path relative to the staged dir."""

    line: int
    """1-indexed line number where the match starts."""

    pattern_name: str
    """Symbolic name of the matched pattern."""

    snippet: str
    """≤200 chars of context around the match. Trimmed for report safety."""


@dataclass
class PreFlightResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    bytes_scanned: int = 0

    @property
    def detected(self) -> bool:
        return bool(self.findings)


# Patterns are intentionally specific. Each one needs to match the
# *combination* of suspicious tokens, not just a single common word. We
# err on the side of false negatives over false positives, since technical
# documentation legitimately contains words like "ignore", "system", "must".
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_previous_instructions",
        re.compile(
            r"ignore\s+(?:all\s+|any\s+|the\s+|your\s+)?previous\s+"
            r"(?:instructions?|prompts?|messages?|directives?)",
            re.IGNORECASE,
        ),
    ),
    (
        "system_override_directive",
        re.compile(
            r"(?:system|admin)\s*[:>]\s*"
            r"(?:override|admin|root|sudo|new\s+task|new\s+role)",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltrate_env_var",
        re.compile(
            r"(?:print|echo|reveal|expose|disclose|include|return|write|"
            r"output|leak|exfiltrat\w+|encode|base64|hex)\s+"
            r"(?:the\s+(?:value\s+of\s+)?)?"
            r"(?:\$?ANTHROPIC_API_KEY|\$?[A-Z_]*API_KEY|\$?[A-Z_]*TOKEN|"
            r"environment\s+variable|/etc/passwd|/etc/shadow|"
            r"~/\.ssh|/proc/self/environ)",
            re.IGNORECASE,
        ),
    ),
    (
        "html_comment_with_directive",
        re.compile(
            r"<!--[^>]{0,500}?"
            r"(?:ignore\s+previous|system\s*:|new\s+task|"
            r"override\s+(?:your|the)|you\s+(?:are|must)\s+now|"
            r"forget\s+(?:previous|all|the)|ANTHROPIC_API_KEY)"
            r"[^>]{0,500}?-->",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "ai_agent_directive",
        re.compile(
            r"(?:dear|to\s+the|attention)\s+"
            r"(?:ai|llm|language\s+model|assistant|agent|claude|gpt)"
            r"[\s,:]+",
            re.IGNORECASE,
        ),
    ),
    (
        "you_are_now_directive",
        re.compile(
            r"you\s+(?:are\s+now|will\s+now|must\s+now|shall|are\s+actually)\s+"
            r"(?:a|an|the)?\s*"
            r"(?:[a-z]+\s+){0,5}?"
            r"(?:assistant|agent|model|jailbroken|unrestricted|dan|"
            r"developer\s+mode)",
            re.IGNORECASE,
        ),
    ),
]


def _snippet(text: str, start: int, end: int, ctx: int = 60) -> str:
    """Return a ≤200-char window around the match, with whitespace
    collapsed for readable single-line report entries."""
    lo = max(0, start - ctx)
    hi = min(len(text), end + ctx)
    raw = text[lo:hi]
    collapsed = re.sub(r"\s+", " ", raw).strip()
    if len(collapsed) > 200:
        collapsed = collapsed[:197] + "..."
    return collapsed


def _line_of(text: str, offset: int) -> int:
    """Return the 1-indexed line number containing the byte offset."""
    return text.count("\n", 0, offset) + 1


def scan_text(text: str, rel_path: str) -> list[Finding]:
    findings: list[Finding] = []
    for name, pat in _PATTERNS:
        for m in pat.finditer(text):
            findings.append(
                Finding(
                    path=rel_path,
                    line=_line_of(text, m.start()),
                    pattern_name=name,
                    snippet=_snippet(text, m.start(), m.end()),
                )
            )
    return findings


def scan_directory(staged_dir: Path) -> PreFlightResult:
    """Scan *.md, *.txt, and tests_newb.{yaml,yml} under staged_dir.

    `staged_dir` is the rw bind-mount target (the temporary copy that will
    be mounted into the container). We scan the host-side copy, not the
    original project dir, so .gitignore filtering has already been applied
    upstream.
    """
    result = PreFlightResult()
    targets: list[Path] = []
    targets.extend(staged_dir.rglob("*.md"))
    targets.extend(staged_dir.rglob("*.txt"))
    targets.extend(staged_dir.rglob("tests_newb.yaml"))
    targets.extend(staged_dir.rglob("tests_newb.yml"))

    for path in targets:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        result.files_scanned += 1
        result.bytes_scanned += len(text.encode("utf-8", errors="replace"))
        rel = str(path.relative_to(staged_dir))
        result.findings.extend(scan_text(text, rel))

    return result


def to_report_section(result: PreFlightResult) -> dict:
    """Render a PreFlightResult as a JSON-serializable report section.

    Goes under report["security"]["pre_flight_scan"].
    """
    return {
        "version": "regex-v1",
        "files_scanned": result.files_scanned,
        "bytes_scanned": result.bytes_scanned,
        "detected": result.detected,
        "findings": [
            {
                "path": f.path,
                "line": f.line,
                "pattern": f.pattern_name,
                "snippet": f.snippet,
            }
            for f in result.findings
        ],
    }


# EOF
