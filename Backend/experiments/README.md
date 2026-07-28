# Reproducible experiments

This package separates research evaluation from production telemetry. Benchmark labels are
synthetic audit-risk proxies, never confirmed fraud.

## Pipeline

```bash
python scripts/generate_benchmark_dataset.py
python scripts/run_all_experiments.py --dry-run
python scripts/run_rule_baseline.py
python scripts/generate_research_report.py
python scripts/check_research_artifacts.py
```

- `configs/`: JSON-compatible YAML with frozen method, provider/model, roles, RAG, debate,
  thresholds, prompt, dataset, seed, timeout, and retry settings.
- `runners/`: normalized result schema and strict candidate-file validation.
- `evaluators/`: label-blind groundedness and citation rubrics plus versioned judge prompts.
- `annotation/`: reviewer schema, adjudication guide, and agreement statistics.
- `metrics.py`, `statistics.py`, `reporting.py`: metrics, uncertainty/tests, reports and figures.
- `results/`: generated artifacts from executed methods only. Missing methods say `Not run`.

Live output must contain exactly one row per frozen evaluation ID with transaction ID, method,
binary prediction, confidence, explanation, evidence IDs, citations, groundedness, citation
correctness, token counts, cost, latency, model, provider, prompt version, run ID, and error.
Each row also records an experiment timestamp, random seed, and resolved-configuration SHA-256;
the immutable resolved configuration is saved beside the run output.
Candidate loading rejects missing/duplicate/unknown IDs and invalid ranges. Groundedness and
citation scores require the documented independent judge or human protocol; judge reasoning is
stored separately and requires human review.

Provider credentials are intentionally optional. Dry-run validates configs and never substitutes
fixture values for live metrics. See `Docs/EXPERIMENT_REPRODUCTION.md` for commands and status.
