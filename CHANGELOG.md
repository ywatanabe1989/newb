# Changelog

All notable changes to newb. Format loosely follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/) with the pre-1.0 caveat
that minor bumps may break.

## [0.19.0] — 2026-05-02

### Changed (BREAKING for forks of `containers/runner.py`)

- **One container per `newb` invocation** instead of one per question.
  Previously, each of the 6 template questions spawned its own
  `docker run --rm`; staged the project; started the SDK; ran one
  query; tore down. For 6 questions that's 6× container startup,
  6× project staging, 6× pip-install (when `post_install_check`
  ran). The new architecture batches all prompts into a single
  container; the in-container runner reads a JSON envelope on
  stdin (`{"prompts": [...]}`), runs each prompt as an independent
  `query()` so conversation context never leaks between answers,
  and emits a JSON envelope on stdout (`{"results": [...]}`).
  On-disk state (e.g. `pip install -e .` from
  `post_install_check`) persists across prompts because the
  container's filesystem persists across the per-prompt
  `query()` calls.
- New `_BaseContainerRunner.run_batch(prompts)`. The single-prompt
  `runner.run(prompt)` is now a thin wrapper around
  `run_batch([prompt])[0]`; existing test seams keep working.
- `_build_argv()` no longer takes a `prompt` arg — argv stops at
  the image tag and the prompt(s) flow via stdin. Forks of
  `containers/runner.py` need to read the JSON envelope from
  stdin or fall back to the legacy single-prompt argv path
  (still supported for back-compat).
- Container timeout is now per-batch and scales with `N` prompts:
  `PER_PROMPT_TIMEOUT_S * len(prompts) + CONTAINER_STARTUP_PAD_S`.

### Why

Empirically, against `scitex-io`: the old per-question architecture
ran 6 separate containers; `post_install_check` would
`pip install -e .` in a cold container that no other question
could see, so the install couldn't actually verify "everything
works after install". The new architecture lets
`post_install_check` write install-state that subsequent prompts
read; running against `scitex-io` now produces
`INSTALL: ok / IMPORT: ok / CLI: ok` with concrete evidence.

## [0.18.1] — 2026-05-02

### Fixed

- **`post_install_check` could never run pip** — the in-container
  SDK was using `permission_mode="acceptEdits"`, which only
  auto-approves edits, so any `Bash` invocation
  (`pip install -e .`, `python -c "import pkg"`, `<pkg> --help`)
  hit a permission prompt and failed in the non-interactive runner.
  Switched to `permission_mode="bypassPermissions"` (SDK equivalent
  of `--dangerously-skip-permissions`) for `--scope all`. Safe
  because the container is the boundary, single-shot, and the
  staged project is the agent's whole filesystem horizon.
  `--scope docs` still uses `acceptEdits` + an `allowed_tools`
  allowlist that excludes `Bash`/`Write`/`Edit`.
- `render_markdown` only emitted 4 of the 6 questions in
  `python-package` and 2 of 6 in `cli-tool`. Added missing branches
  for `post_install_check`, `prompt_injection_check`,
  `install_and_help`, `subcommand_tree`, `typical_usage`,
  `common_pitfall`.

## [0.18.0] — 2026-05-02

### Decided not to do

- **Hooks injection via `[tool.newb]`** — considered as a sibling to
  `mcp_servers` and dropped from scope. Inside `--scope all` the
  agent already has full Bash, so a `[tool.newb] hooks` table adds
  no capability the agent doesn't already have; it only adds a
  second config surface to maintain. If a future use case actually
  needs lifecycle hooks (e.g. capturing `PostToolUse` for
  auditing), revisit then with the same validator pattern as
  `mcp_servers`.

### Added

- `mcp_servers` is now a recognized `[tool.newb]` key. The table is
  validated host-side (`_mcp_inject.validate`) and JSON-encoded into
  `NEWB_MCP_SERVERS_JSON`, which the in-container `runner.py` decodes
  and feeds to `ClaudeAgentOptions(mcp_servers=...)`. Lets a project
  pin its preferred MCP servers (filesystem, scitex, etc.) so the
  newb agent has the same tool surface as a normal Claude Code
  session.
- Validation rules: identifier-shaped keys; `type` ∈
  `stdio | http | sse`; for `stdio`, `command` must be a basename
  (resolved on the container's PATH) or an absolute path beginning
  with `/usr/`, `/bin/`, `/sbin/`, `/work/`, `/opt/`, `/etc/`.
  Host-relative paths are rejected because they won't resolve inside
  the container.
- New module: `newb._mcp_inject` (`validate`, `encode_env`,
  `McpInjectError`).

## [0.17.1] — 2026-05-02

### Added

- `install_mode` is now a recognized `[tool.newb]` key in
  `pyproject.toml`. Default-resolution order matches the other keys:
  CLI flag > pyproject value > built-in default (`editable`). Lets a
  package pin `install_mode = "wheel"` for release-sanity verification
  without per-invocation flags.

## [0.17.0] — 2026-05-02

### Added

- `NEWB_ENV_SRC` env-loader (SciTeX ecosystem standard). Point at a
  `.src` file (or directory of `.src` files) and `newb` auto-loads
  `NEWB_*` env vars at CLI / MCP-server startup. Lets users keep
  auth + hardening config in their shell profile instead of
  per-shell `export` lines.
- `newb env-template [-o PATH]` — emits a copy-pasteable `.src`
  file listing every `NEWB_*` env var with description + commented
  example. Single source of truth in `_env_registry.REGISTRY`.

### Fixed

- Subcommand routing: `newb templates list`, `newb skills list`,
  `newb mcp list-tools`, `newb env-template`, etc. all work again.
  The optional SOURCE positional on the top-level group was
  greedily eating subcommand names; the new `_NewbGroup.parse_args`
  peeks at the first positional and yields to subcommand
  resolution when it matches a registered command.

## [0.16.1] — 2026-05-02

### Fixed

- `ApptainerRunner` now picks up `NEWB_HARDEN_*` / `--harden-*` flags.
  Previously the `hardening` argument was silently ignored on
  `--runtime apptainer`.

### Added

- `apptainer_hardening_argv()` — best-effort parity with
  `hardening_argv()` for the docker→apptainer flag subset that maps
  cleanly (`--memory`, `--cpus`, `--pids-limit`, `--net --network none`).
- Apptainer-specific limits (capability drop, no-new-privileges, tmpfs
  noexec) intentionally not mapped — apptainer's rootless model handles
  most of those at the user-namespace layer.

## [0.16.0] — 2026-05-02

### Added

- `--install-mode {editable | wheel | pypi}` — controls how the agent
  installs the package during `post_install_check`.
  - `editable` (default): `pip install -e .` (dev loop)
  - `wheel`: build a wheel and install it (release sanity)
  - `pypi`: `pip install <pkg-name>` (real-user reproduction)
- Surfaced in `runtime_info`. Wired through `run() → prompt.format(...)`.

## [0.15.0] — 2026-05-02

### Added

- **pytest-style author-test discovery**:
  - `tests_newb.yaml` (existing canonical YAML)
  - `tests_newb.py` — module exporting `TESTS = [...]` (list of dicts
    in the same schema as YAML)
  - `test_newb_*.py` — globbed pytest-style additional modules
  - All sources concatenated; YAML first, then `.py`.
- **`[tool.newb]` in `pyproject.toml`** — project-level defaults for
  `template`, `runtime`, `scope`, `model`, `runs`. Walks up from source
  dir to find the config. CLI flags win when explicitly different from
  built-in defaults; pyproject overrides the built-in default. Unknown
  keys silently ignored (forward-compat).

## [0.14.0] — 2026-05-02

### Added

- `--runtime podman` — rootless container without a docker daemon.
  Argv-compatible with docker; `PodmanRunner` subclasses `DockerRunner`
  and only swaps the leading binary name.

## [0.13.0] — 2026-05-02

### Added

- **`--scope {all | docs}`** — agent scope.
  - `all` (default): full agentic permissions (no `allowed_tools`
    restriction; `permission_mode="acceptEdits"` carries the policy).
    Agent can install/run/test the package — newb's core value.
  - `docs`: read-only audit mode (`Read`, `Glob`, `Grep` only).
- **Transparency report header** — every report (markdown + JSON)
  includes a `runtime_info` block: `newb_version`, `runtime`, `image`,
  `model`, `template`, `scope`, `skills_path`, `agent_resources`,
  `setting_sources`, hardening summary. Pytest-style runtime-settings
  block at the top of the markdown so users see exactly what the agent
  saw.
- **`--harden-*` CLI flags** — `--harden-memory`, `--harden-cpus`,
  `--harden-pids-limit`, `--harden-no-network`, `--harden-tmpfs-noexec`.
  Wired through to `HardeningOptions` with three-layer resolution
  (`kwargs > NEWB_HARDEN_* env > defaults`).

### Changed

- `_cli.py` refactored from 576 lines into sibling modules
  (`_cli_templates.py`, `_cli_skills.py`, `_cli_mcp.py`); public
  surface (`from newb._cli import main, cli_entrypoint`) preserved.
- `_try.py` refactored from 534 lines: extracted `_grading.py`
  (test loading + grading) and `_runtime_info.py` (header builder).
  Public surface (`run`, `render_markdown`, `_load_tests`) preserved.

## [0.12.0] — 2026-05-02

### **BREAKING**

Pre-1.0 cleanup. Simplicity over compat.

- Removed `newb.self_explain` alias (use `newb.run` or bare-module callable).
- Removed `newb_self_explain` MCP tool.
- Removed `_PROMPT_*` re-exports in `_try.py` (templates now live in
  `question_templates/<name>.py`).
- Removed `_load_red_tests` shim, `_red_tests.yaml` legacy filename,
  `question:` key alias for `prompt:`, `red_tests` duplicate key in
  report, `_validate_skills_dir` alias.

## [0.11.0] — 2026-05-02

### Added

- **Configurable container hardening** — `HardeningOptions` dataclass.
  Defaults: `--cap-drop=ALL`, `--security-opt=no-new-privileges`,
  `--network=bridge`. Resource caps **off by default** so the agent
  can install/run/test the package.
- `NEWB_HARDEN_*` env vars opt in to stricter caps (memory, cpus,
  pids-limit, tmpfs noexec, no-network).
- `docs/security/threat-model.md` — Rule-of-Two analysis, T1-T5 threat
  classes, per-version posture table.
- `## Security disclaimer` section in README.
- Optional `newb[security]` extra (transformers + torch + sentencepiece)
  for `protectai/deberta-v3-base-prompt-injection-v2` pre-flight scan.

## [0.10.2] — 2026-05-02

### Fixed

- Auth flow collapsed to single `NEWB_ANTHROPIC_API_KEY` env var.
  No more `_OAUTH` split. The Anthropic backend accepts both
  `sk-ant-api*` (real API keys) and `sk-ant-oat*` (Claude Code OAuth
  access tokens) on the same Authorization header — newb forwards
  the value verbatim into the container.

---

## Earlier releases

See git log for 0.x.x history before this changelog was added.

- **0.10.0** — pivot to claude-agent-sdk (Anthropic official) as runtime
- **0.10.0** — `_verify.py` → `_try.py` rename, lift `.md`-only restriction
- **0.9.x** — drop `host` runtime; only `docker` / `apptainer`
- **0.8.0** — docker + apptainer runtimes for hard isolation
- **0.7.0** — pivot to `claude-agent-sdk`
- **0.6.0** — pivot to `scitex-agent-container` runtime
