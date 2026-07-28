# Threats to validity

- Construct validity: generator labels encode control scenarios, not confirmed fraud; heuristic
  confidence and model judges may not measure audit correctness.
- Internal validity: prompts, caching, provider fallback, retrieval corpus, and thresholds can
  confound agent-role effects. Frozen configs and paired IDs reduce but do not remove this.
- External validity: synthetic US-dollar records do not represent industries, jurisdictions,
  currencies, controls, prevalence, language, or adversaries in production.
- Statistical validity: a roughly 116-row evaluation split limits category power. Single-class
  category slices make some metrics undefined. Multiple comparisons require correction.
- Reproducibility: provider models can change despite stable names; record timestamps, resolved
  configs, usage, and provider/model identifiers. Rule micro-latency varies by host.
- Evaluation bias: LLM judges can share failure modes with evaluated models. Human review and
  agreement reporting are required; neither has yet been executed.
