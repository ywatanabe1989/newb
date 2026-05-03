"""Declarative CI gate — evaluate a newb report against pyproject criteria.

Reads ``[tool.newb.gate]`` from ``pyproject.toml`` (nested by question
key) and checks whether the corresponding ``<key>_parsed`` fields in a
report match. Intended target audience: CI pipelines that want a single
exit code instead of bespoke ``jq`` chains.

Default criteria (used when no ``[tool.newb.gate]`` table is present):

  post_install_check.install == "ok"
  post_install_check.import  == "ok"
  prompt_injection_check.found == false

Config shape::

    [tool.newb.gate.post_install_check]
    install = "ok"
    import  = "ok"
    cli     = ["ok", "n/a"]   # list = any-of

    [tool.newb.gate.prompt_injection_check]
    found = false

Lists mean "any value in this list passes". Scalars must match exactly.
``runs_per_prompt > 1`` reports produce a list of parsed dicts; the gate
requires ALL runs to pass (worst-case).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_GATE: Dict[str, Dict[str, Any]] = {
    "post_install_check": {"install": "ok", "import": "ok"},
    "prompt_injection_check": {"found": False},
}


def load_gate_config(pyproject_dir: Path | str) -> Dict[str, Dict[str, Any]]:
    """Resolve effective gate criteria: pyproject > defaults.

    Returns a dict ``{question_key: {field: required_value_or_list}}``.
    """
    from ._pyproject_config import load_pyproject_config

    cfg = load_pyproject_config(pyproject_dir)
    gate = cfg.get("gate") if isinstance(cfg, dict) else None
    if not isinstance(gate, dict) or not gate:
        return {k: dict(v) for k, v in DEFAULT_GATE.items()}
    out: Dict[str, Dict[str, Any]] = {}
    for q, spec in gate.items():
        if isinstance(spec, dict):
            out[q] = dict(spec)
    return out or {k: dict(v) for k, v in DEFAULT_GATE.items()}


def _matches(actual: Any, required: Any) -> bool:
    """Scalar = exact match; list = any-of."""
    if isinstance(required, list):
        return actual in required
    return actual == required


def _check_one(parsed: Dict[str, Any], spec: Dict[str, Any], qkey: str) -> List[str]:
    failures: List[str] = []
    for field, required in spec.items():
        if field not in parsed:
            failures.append(
                f"{qkey}.{field}: missing in report (got keys: {sorted(parsed.keys())})"
            )
            continue
        if not _matches(parsed[field], required):
            failures.append(
                f"{qkey}.{field}: expected {required!r}, got {parsed[field]!r}"
            )
    return failures


def evaluate(
    report: Dict[str, Any],
    gate: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[bool, List[str]]:
    """Evaluate a parsed-report dict against gate criteria.

    ``gate`` defaults to ``DEFAULT_GATE`` when ``None``. Each question's
    ``<key>_parsed`` field is consulted; a list there (from
    ``runs_per_prompt > 1``) requires every run to pass.

    Returns ``(passed, failures)``. ``passed`` is True only when
    ``failures`` is empty.
    """
    if gate is None:
        gate = DEFAULT_GATE
    failures: List[str] = []
    for qkey, spec in gate.items():
        parsed = report.get(f"{qkey}_parsed")
        if parsed is None:
            failures.append(f"{qkey}_parsed: absent from report")
            continue
        if isinstance(parsed, list):
            for i, entry in enumerate(parsed):
                if not isinstance(entry, dict):
                    failures.append(f"{qkey}_parsed[{i}]: not a dict")
                    continue
                for f in _check_one(entry, spec, f"{qkey}[{i}]"):
                    failures.append(f)
        elif isinstance(parsed, dict):
            failures.extend(_check_one(parsed, spec, qkey))
        else:
            failures.append(f"{qkey}_parsed: not a dict or list")
    return (not failures), failures


# EOF
