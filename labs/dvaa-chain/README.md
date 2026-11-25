# labs/dvaa-chain

Instrumented run of DVAA 0.9.2 scenario `a2a-trust-chain-poisoning/vulnerable`
(OASB SS-08). Agent cards of all three agents are clean; the poisoning happens
on the edge, inside the manager hop. hopscope observes that edge on real traffic.

## Topology

    host 127.0.0.1:3130
      -> orchestrator          (DVAA code, unchanged)
      -> manager-tap           alias "manager", records ingress -> out/manager.in.jsonl
      -> dvaa-manager          (DVAA code, unchanged, poisons the task)
      -> worker-sink           alias "worker", records egress  -> out/manager.out.jsonl

DVAA hardcodes `http://manager:3131` and `http://worker:3132`; network aliases
satisfy that without patching DVAA. The DVAA worker is replaced by a sink that
records and answers, it never follows instructions from `context`.

## Run

    cd labs/dvaa-chain
    HOPSCOPE_UID=$(id -u) HOPSCOPE_GID=$(id -g) docker compose up -d
    curl -s -X POST 127.0.0.1:3130/analyze -H 'content-type: application/json' -d '{"quarter":"Q1"}'
    docker compose down

Ground truth is `out/*.jsonl`, not the `/analyze` response: the manager filters
its reply to the orchestrator (drops `executedWith` and credential findings).

## Safety

- Image pinned by digest, `read_only`, `cap_drop: ALL`, `no-new-privileges`, mem/pids limits.
- Only orchestrator is published, on `127.0.0.1`. Never use a bare `-p PORT:PORT`:
  Docker-published ports bypass ufw.
- Network `chain` is `internal: true`: manager and sink have no route out.
- Do not run the scenario's own `docker-compose.yml`: it publishes on all interfaces.
