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
