# Changelog

## [0.1.0] - 2026-11-23

First public release: a deterministic, adversarial measurement range for authority creep in
multi-hop A2A delegation chains. Companion to the PPD pre-registration (10.5281/zenodo.23513214).

### Added
- Reference four-hop chain (orchestrator → planner → worker → executor), in-process and over
  A2A JSON-RPC (`a2a-sdk` 1.x) through an in-process ASGI transport, no sockets.
- Simulated tools (fs, secrets, payments, net) with `domain:action:resource` capabilities, canary
  secrets and an exfiltration outbox; network access forbidden in tests and audited by import.
- Static authority tiers T0 ⊂ T1 ⊂ T2 for the executor and a deterministic gate ruling every call
  `IN_MANDATE`, `CANDIDATE` (PPD D7(i)-(ii)) or `ESCALATION`; escalations never execute.
- Attenuation levels A0 (none), A1 (requested ∩ held, binding on tools) and A2 (HMAC delegation
  tokens bound to run and receiver).
- Adversarial scenarios: over-delegation, compromised-worker, poisoned-card.
- Metrics CIR, ESR, EXR with Wilson intervals (explicitly not MIR); exploratory λ_exc and λ_div.
- Scenario × attenuation matrix, generated into the README and checked by a test.
- Reports: JSONL run journal, SARIF 2.1.0 (HSC001-HSC004), self-contained HTML.
- Live mode scaffold on Ollama following PPD v0.5 §5 (fresh load per agent, derived seeds,
  shipped sampling, `truncate`/`shift` off), refused while the GPU is reserved for PPD.
- Sealed container for the deterministic range; external A2A target scaffold, local-only by default.
