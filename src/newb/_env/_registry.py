#!/usr/bin/env python3
"""Registry of all NEWB_* env vars + ``generate_template()``.

Single source of truth for newb's env-var surface. Used by:

- ``newb show-env-template`` — emits a copy-pasteable ``.src`` file
- docs (referenced from skills + README)
- forward-compat / introspection
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvVar:
    name: str
    description: str
    default: str = ""
    example: str = ""
    category: str = "misc"
    secret: bool = False


REGISTRY: list[EnvVar] = [
    # --- auth ---
    EnvVar(
        name="NEWB_ANTHROPIC_API_KEY",
        category="auth",
        secret=True,
        description=(
            "Opaque token forwarded into the container. Accepts both "
            "sk-ant-api03-… (real API key) and sk-ant-oat01-… (Claude "
            "Code OAuth access token) on the same code path."
        ),
        example="sk-ant-api03-...",
    ),
    EnvVar(
        name="NEWB_CLAUDE_CODE_CREDENTIALS_JSON",
        category="auth",
        secret=True,
        description=(
            "Full ~/.claude/.credentials.json content as the env-var "
            "value (refresh_token + accessToken + expiresAt + scopes + "
            "subscriptionType). When set, newb materialises it to a "
            "0644 tempfile and bind-mounts it into the container, so "
            "the SDK uses the file-based credentials_file flow. "
            "Required for OAuth flat-rate billing in CI; Anthropic "
            "rejects sk-ant-oat01-… tokens passed as a bare env var. "
            "Real sk-ant-api* keys can use NEWB_ANTHROPIC_API_KEY "
            "alone; this var is for OAuth-only paths."
        ),
        example='{"claudeAiOauth":{"accessToken":"sk-ant-oat01-…",…}}',
    ),
    # --- runtime ---
    EnvVar(
        name="NEWB_DOCKER_IMAGE",
        category="runtime",
        description=(
            "Override the container image used by --runtime docker / "
            "podman / apptainer. Pinned to ghcr.io/.../newb-runner:<newb_version> "
            "by default."
        ),
        example="ghcr.io/myorg/newb-runner:latest",
    ),
    EnvVar(
        name="NEWB_MODEL",
        category="runtime",
        description="Override the Claude model id passed to the SDK.",
        default="claude-haiku-4-5",
    ),
    EnvVar(
        name="NEWB_SCOPE",
        category="runtime",
        description=(
            "Agent scope: 'all' (full agentic) or 'docs' (read-only audit). "
            "Set inside the container by the host runner; users normally "
            "use the --scope CLI flag instead."
        ),
        default="all",
    ),
    EnvVar(
        name="NEWB_CWD",
        category="runtime",
        description="Working directory the SDK uses inside the container.",
        default="/work/project",
    ),
    EnvVar(
        name="NEWB_SKILLS_PATH",
        category="runtime",
        description=(
            "Absolute path inside the container of the focused docs subdir; "
            "interpolated into prompts via {skills_path}."
        ),
        default="/work/project",
    ),
    # --- hardening ---
    EnvVar(
        name="NEWB_HARDEN_CAP_DROP_ALL",
        category="hardening",
        description="Drop all Linux kernel capabilities. Default on.",
        default="1",
    ),
    EnvVar(
        name="NEWB_HARDEN_NO_NEW_PRIVS",
        category="hardening",
        description="Block setuid privilege escalation. Default on.",
        default="1",
    ),
    EnvVar(
        name="NEWB_HARDEN_NO_NETWORK",
        category="hardening",
        description=(
            "If 1, --network=none (breaks pip + SDK; only for offline workflows). "
            "Default 0 = bridge network."
        ),
        default="0",
    ),
    EnvVar(
        name="NEWB_HARDEN_MEMORY",
        category="hardening",
        description="Container memory cap, e.g. '4g'. Default unlimited.",
        example="4g",
    ),
    EnvVar(
        name="NEWB_HARDEN_MEMORY_SWAP",
        category="hardening",
        description="Container memory-swap cap. Default unlimited.",
        example="4g",
    ),
    EnvVar(
        name="NEWB_HARDEN_CPUS",
        category="hardening",
        description="Container CPU cap (cores). Default unlimited.",
        example="2",
    ),
    EnvVar(
        name="NEWB_HARDEN_PIDS_LIMIT",
        category="hardening",
        description="Container PID cap. Default unlimited.",
        example="256",
    ),
    EnvVar(
        name="NEWB_HARDEN_TMPFS_NOEXEC",
        category="hardening",
        description=(
            "If 1, mount /tmp with noexec,nosuid. Default off — pip and "
            "pytest sometimes write+exec wheels in /tmp."
        ),
        default="0",
    ),
    # --- meta ---
    EnvVar(
        name="NEWB_PIP_CACHE_DIR",
        category="meta",
        description=(
            "Host directory mounted into the container as the agent's "
            "pip cache (~/.cache/pip). Speeds up local-dev iteration "
            "by skipping wheel re-downloads on repeated `newb` runs. "
            "Leave unset for CI — cold install is the honest newbie "
            "test."
        ),
        example="~/.cache/newb-pip",
    ),
    EnvVar(
        name="NEWB_ENV_SRC",
        category="meta",
        description=(
            "Path to a .src file (or directory of .src files) that "
            "newb sources at startup. Standard SciTeX env-loader pattern."
        ),
        example="~/.scitex/newb/local.src",
    ),
]


def generate_template() -> str:
    """Render the registry as a copy-pasteable ``.src`` file."""
    lines: list[str] = [
        "# newb environment variables — generated by `newb show-env-template`",
        "# Source this file from your shell profile, or point",
        "# NEWB_ENV_SRC at it so newb auto-loads on startup.",
        "",
    ]
    by_category: dict[str, list[EnvVar]] = {}
    for var in REGISTRY:
        by_category.setdefault(var.category, []).append(var)
    for category in ("auth", "runtime", "hardening", "meta"):
        if category not in by_category:
            continue
        lines.append(f"# ---- {category} ----")
        for var in by_category[category]:
            lines.append(f"# {var.description}")
            value = var.example or var.default
            if var.secret:
                lines.append(f"# export {var.name}={value or '<set-me>'}")
            elif value:
                lines.append(f"# export {var.name}={value}")
            else:
                lines.append(f"# export {var.name}=")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# EOF
