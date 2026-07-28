# Experiment reproduction

Use Python 3.11 from `Backend/` after `pip install -r requirements.txt`:

```bash
python scripts/generate_benchmark_dataset.py
python scripts/run_all_experiments.py --dry-run
python scripts/run_rule_baseline.py
python scripts/generate_research_report.py
python -m pytest tests/test_research_pipeline.py
```

The manifest SHA-256 verifies data regeneration. Live runs require the selected provider API key
and `USE_REAL_AGENTS=true`; run `python scripts/run_single_llm.py`,
`python scripts/run_multi_agent.py`, or `python scripts/run_ablation.py
experiments/configs/no_verifier.yaml`. These commands currently validate readiness and state
`Not run`; production API output must be exported through the normalized candidate schema before
scoring. Never use dry-run fixtures as research results.
