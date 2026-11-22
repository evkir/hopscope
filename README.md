# hopscope

**Measurement range for mandate inflation (MIR) in multi-agent A2A delegation chains.**

> Status: pre-alpha (planning). Part of [MASec Lab](https://maseclab.com).

hopscope runs a reference multi-hop agent system (orchestrator → planner → worker → executor)
with **simulated tools only** and measures how much authority grows at each delegation hop:
MIR distribution over ensembles of runs, inflation rate λ_inf and trajectory divergence λ_div,
across attenuation levels (A0 none · A1 scope string · A2 token exchange).

Research basis: *Privilege-Differential Drift: Measuring Mandate Inflation in Hierarchical
LLM Agent Systems* — [10.5281/zenodo.23513214](https://doi.org/10.5281/zenodo.23513214).

Maps to OWASP Top 10 for Agentic Applications: ASI03, ASI07, ASI08.

## License
Apache-2.0
