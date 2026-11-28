# External A2A targets

hopscope v0.1 measures its own reference chain. External targets are scaffolded, not driven:
`hopscope.targets` holds their configuration and refuses anything that is not local.

| Target | Card | Notes |
|---|---|---|
| `dvaa-a` | `http://127.0.0.1:7020/.well-known/agent-card.json` | Damn Vulnerable AI Agent, run locally |
| `dvaa-b` | `http://127.0.0.1:7021/.well-known/agent-card.json` | Damn Vulnerable AI Agent, run locally |

Rules:

- Only loopback, `localhost`, `*.localhost` and `*.test` hosts pass `check_target` by default.
- Any other host needs `allow_remote=True`. Use it only for systems you own or hold written
  authorisation to test; hopscope cannot verify that for you.
- Verify the card path against your local build before pointing anything at it.

Planned for v0.2: a probe that reads a target's AgentCard, maps its skills onto hopscope's
capability grammar and replays the three scenarios against it.

## DVAA 0.9.2: what the probe found (2026-11-24)

Image `opena2a/dvaa:0.9.2@sha256:edcd7fbb94b28be64527b58f7238384d58d9b0b015b6ab02cd7f816c7f696f45`.
Run it bound to loopback only:

    docker run -d --rm --name dvaa -p 127.0.0.1:9000:9000 -p 127.0.0.1:7020:7020 -p 127.0.0.1:7021:7021 opena2a/dvaa:0.9.2

A plain `-p 7020:7020` publishes on every interface, and Docker's iptables rules bypass ufw. The
scenario compose files inside the image (`/app/scenarios/*/vulnerable/docker-compose.yml`) use plain
`"PORT:PORT"` mappings: do not run them unmodified.

- The fleet's A2A agents (Orchestrator :7020, Worker Agent :7021) publish no AgentCard; both
  well-known paths return 404. `hopscope probe dvaa-a|dvaa-b` synthesizes a card from the dashboard's
  `/agents` API and reports `card_source: dvaa-dashboard`. Worker Agent reads as T2
  (read_file T0, write_file T1, fetch_url T2).
- The A2A scenario agents publish cards at the pre-0.3 path `/.well-known/agent.json`, with
  capabilities as a bare string list; the probe reads those strings as skills.
- In `a2a-trust-chain-poisoning` every card is benign. The compromised manager escalates the forwarded
  task's `permissions` to `read-write, execute, network-access` and injects "approved elevated access"
  context. A card-level reading cannot see this: it is excess on the delegation edge, which is what
  hopscope measures.

## DVAA chain lab: the manager edge (2026-11-26)

DVAA 0.9.2 hard-codes its delegation chain (`manager:3131`, `worker:3132`). `labs/dvaa-chain` runs it
unmodified from the pinned image and puts recorders around the manager through network aliases:

The tap records what the manager received and forwards it; the sink records what the manager handed on
and answers like a worker without following the task context, so nothing leaves the lab. The chain
network is `internal`; only the orchestrator is published, on loopback.

```bash
(cd labs/dvaa-chain && HOPSCOPE_UID=$(id -u) HOPSCOPE_GID=$(id -g) docker compose up -d)
hopscope probe dvaa-chain --sarif dvaa-chain.sarif
docker compose -f labs/dvaa-chain/compose.yml down
```

`probe dvaa-chain` posts `{"quarter": "Q1"}` to `/analyze` once and reads only the tasks recorded after
that POST; earlier runs in `out/` are left in place as ground truth. Exit 0 read, 3 refused, 4 error or
unmatched hop.

| | received (held) | handed on (granted) |
|---|---|---|
| DVAA labels | `read-only` | `read-write`, `network-access`, `execute` |
| capabilities | `fs:read:/workspace/*` | `fs:read:/workspace/*`, `fs:write:/workspace/*`, `net:fetch:*`, `net:post:*` |
| tier | T0 | T2 |

Live reading of 2026-11-26 (task `orch-1795680728551`, same as the fixture in
`tests/fixtures/dvaa/0.9.2/chain/`):

- excess: `fs:write:/workspace/*`, `net:fetch:*`, `net:post:*`; out of vocabulary added: `exec` -> HSC004;
- origin rewritten (`from` no longer the orchestrator);
- context appended, 53 -> 359 characters (only length and sha256 are kept);
- hidden field `_originalPermissions` added on egress.

The manager filters its answer to the orchestrator (drops `executedWith` and credential findings), so
the orchestrator's own view shows no escalation: the wire records are the ground truth.

`network-access` maps to `net:fetch:*` plus `net:post:*` rather than `net:*:*`, because a wildcard action
is a grant template and has no tier. `execute` has no capability in the range's vocabulary and is kept
as the out-of-vocabulary label `exec`, the same label the grammar uses for cards.

HSC005 (`DelegationTampering`, level note) covers the rest of the edge: a hop that tampers with the
task (origin, context, hidden `_` fields) while handing on no more authority than it held. The two
rules are exclusive per edge: any excess or added out-of-vocabulary permission makes it HSC004, with
the tampering flags kept in `properties`. The DVAA manager edge escalates, so it reads as HSC004 only;
HSC005 is exercised on synthetic edges in `tests/test_probe_chain_sarif.py`.
