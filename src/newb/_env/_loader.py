#!/usr/bin/env python3
"""Environment variable loader for ``NEWB_ENV_SRC``.

Parses bash-compatible ``.src`` files containing environment-variable
definitions. Supports both a directory path (all ``*.src`` files in
order) and a single file path.

Pattern follows the SciTeX ecosystem standard (see
``scitex-audio/_env_loader.py``); enables the newb CLI / MCP server to
pick up auth, hardening, and runtime defaults from a centralized shell
profile without requiring per-shell ``export`` lines.

Recognized syntax::

    # comment line
    export NEWB_ANTHROPIC_API_KEY="sk-ant-..."
    NEWB_HARDEN_MEMORY=4g
    NEWB_HARDEN_CPUS=${HOST_CPUS}     # variable expansion

Quoted values support ``\\"``, ``\\$``, and ``\\\\`` escapes. Lines
that don't match are silently ignored (forward-compat).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

_ENV_VAR = "NEWB_ENV_SRC"

_ENV_PATTERN = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def _parse_value(value: str) -> str:
    """Parse a bash-style value: strip quotes, expand ``$VAR`` / ``${VAR}``."""
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
        value = value.replace('\\"', '"')
        value = value.replace("\\$", "$")
        value = value.replace("\\\\", "\\")
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]

    def expand_var(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    value = re.sub(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)", expand_var, value)
    return value


def parse_src_file(filepath: Path) -> Dict[str, str]:
    """Return the env-var dict declared in one ``.src`` file."""
    env_vars: Dict[str, str] = {}
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match = _ENV_PATTERN.match(line)
                if match:
                    name, value = match.groups()
                    env_vars[name] = _parse_value(value)
    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
    return env_vars


def load_env_from_path(path: str) -> Dict[str, str]:
    """Load env vars from a file or directory of ``.src`` files."""
    loaded: Dict[str, str] = {}
    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        logger.warning(f"{_ENV_VAR} path does not exist: {path}")
        return loaded

    files_to_load: List[Path] = []
    if path_obj.is_dir():
        files_to_load = sorted(path_obj.glob("*.src"))
    elif path_obj.is_file():
        files_to_load = [path_obj]
    else:
        logger.warning(f"{_ENV_VAR} is not a file or directory: {path}")
        return loaded

    for src_file in files_to_load:
        env_vars = parse_src_file(src_file)
        if env_vars:
            logger.info(f"Loaded {len(env_vars)} vars from {src_file.name}")
            loaded.update(env_vars)
    return loaded


def load_newb_env() -> int:
    """Load env vars from ``NEWB_ENV_SRC`` (if set). Returns count loaded.

    Call this early in CLI / MCP-server startup so all subsequent reads
    of ``NEWB_*`` env vars see the unified, shell-profile-controlled
    configuration. No-op when ``NEWB_ENV_SRC`` is unset.
    """
    env_src = os.environ.get(_ENV_VAR)
    if not env_src:
        return 0
    loaded = load_env_from_path(env_src)
    for name, value in loaded.items():
        os.environ[name] = value
    if loaded:
        logger.info(f"{_ENV_VAR}: Loaded {len(loaded)} environment variables")
    return len(loaded)


# EOF
