# Changelog

## [Unreleased]

### Added
- `hopscope probe TARGET`: reads an external AgentCard (local targets only) into implied and solicited
  capabilities and a T0-T2 tier; JSON (`hopscope.probe/v1`) or terminal-safe text; exit 3 refused, 4 error.
- Guarded card fetch: the target and every URL the card advertises are checked, redirects refused,
  environment proxies ignored, body capped at 256 KiB. Reports carry no card prose.
- Card discovery at both well-known paths (`agent-card.json`, then pre-0.3 `agent.json`); tolerant parser
  for v0.3/v1.0 cards and legacy string-list capabilities.
- DVAA adapter: DVAA 0.9.2's A2A agents publish no card, so `dvaa-a` / `dvaa-b` synthesize one from the
  dashboard API, reported as `card_source: dvaa-dashboard`.
- DVAA 0.9.2 scenario card fixtures and probe findings in `docs/targets.md`.
- `labs/dvaa-chain`: DVAA 0.9.2 orchestrator -> manager -> worker under docker compose, published on
  127.0.0.1 only (internal chain network, read-only, all capabilities dropped), with a recorder tap
  before the manager and a sink after it that never follows task context. No DVAA code is copied.
- Chain reading (`hopscope.probe.chain/v1`): per hop, the excess handed on beyond what the hop held,
  added out-of-vocabulary permissions, rewritten origin, appended or rewritten context (length and a
  short sha256 only, never the text) and hidden `_` fields.
- `hopscope probe dvaa-chain [--json] [--sarif FILE] [--records DIR]`: one POST to the lab, then only
  hops recorded after that POST are read; HSC004 SARIF for escalated hops; `--sarif` on a card target
  exits 2.
- `dvaa` pytest marker (deselected by default, `pytest -m dvaa`): brings the lab up and asserts HSC004
  on the manager edge. The test network guard gives dvaa-marked tests loopback only.

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
