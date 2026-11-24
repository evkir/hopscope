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
