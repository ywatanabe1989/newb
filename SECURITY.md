# Security

newb runs an AI agent against arbitrary package documentation, which
is an unsolved-by-default attack surface. Read this before running
newb on packages you don't fully control.

For the full Rule-of-Two analysis, see
[`docs/security/threat-model.md`](docs/security/threat-model.md).

To **report a vulnerability**: please open a private security advisory
on the [GitHub repository](https://github.com/ywatanabe1989/newb)
rather than a public issue.

## Threats we recognize

- **Indirect prompt injection** via package READMEs, docstrings, and
  `tests_newb.yaml`. The agent reads untrusted text by design — that's
  newb's whole job.
- **API key exfiltration** via agent output (`/proc/self/environ`,
  encoded leaks, the agent being convinced to print the key).
- **Container escape** attempts (kernel CVEs, capability
  misconfiguration).
- **Network exfiltration** to attacker-controlled hosts.
- **Resource exhaustion** (fork bombs, memory hogs).

## What newb implements

- **Container is the boundary** — Docker / Podman / Apptainer with
  `--cap-drop=ALL`, `--security-opt=no-new-privileges`, default
  `--network=bridge`. The container is `--rm`'d after every run.
- **Configurable hardening** — opt-in resource caps
  (`--harden-memory`, `--harden-cpus`, `--harden-pids-limit`),
  `--harden-no-network` for fully offline runs, all wired via
  `NEWB_HARDEN_*` env vars or CLI flags.
- **No host `~/.claude/` leak** — the in-container SDK runs with
  `setting_sources=[]`, so the host's `CLAUDE.md`, agent context,
  and login session never reach the agent.
- **NEWB-prefixed env namespace** — newb never silently inherits the
  upstream `ANTHROPIC_API_KEY`. The host runner actively masks it for
  the duration of the SDK call. One opt-in env var:
  `NEWB_ANTHROPIC_API_KEY`.
- **Optional `newb[security]` extra** — Protect AI's
  `deberta-v3-base-prompt-injection-v2` for pre-flight scanning of
  staged docs.
- **`prompt_injection_check` question** — the agent itself reports
  adversarial content it noticed during the run. Useful as a
  consistency signal, not a guarantee.

## What newb cannot promise

- **Prompt injection is unsolved at the model level.** Per Meta's
  [Agents Rule of Two](https://ai.meta.com/blog/practical-ai-agent-security/)
  and OWASP LLM01, research consensus reports >85% attack success
  against state-of-the-art defenses with adaptive attacks.
- Sophisticated, novel, or encoded injection attempts may bypass
  every layer above.
- We cannot accept responsibility for any consequence of running newb
  against untrusted package documentation.

## Operating recommendations

- **Pin** a specific newb version and image digest in CI.
- Treat verdicts on **adversarially-authored** packages as heuristic
  only.
- **Never** run newb with credentials beyond what a single dev-loop
  verification needs. Don't reuse production keys.
- For ecosystem-wide CI matrices, prefer a dedicated low-privilege
  Anthropic key with a tight quota.
- Audit `tests_newb.yaml` like you audit any third-party config — its
  prompts run with full agent capabilities.
