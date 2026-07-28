# Reproducible experiments

Run the fixed, leakage-controlled evaluation split from `Backend/`:

```bash
python scripts/evaluate_experiments.py
```

The bundled dataset is synthetic. `risk_hint != normal` is an **anomaly proxy
label**, not confirmed fraud. The label column is never passed to a method.
Rows are assigned to an 80% development and 20% held-out evaluation partition
by SHA-256 of a fixed seed and transaction ID.

To score a single-LLM, multi-agent, or ablation run, export one CSV per method:

```text
transaction_id,prediction,groundedness,citation_correctness,cost_usd,latency_ms
TRX-000001,true,0.9,1.0,0.012,8420
```

Then run:

```bash
python scripts/evaluate_experiments.py --predictions experiments/runs/multi_agent.csv
```

Every held-out transaction must have a prediction; this prevents selective
reporting. `groundedness` and `citation_correctness` must come from a documented
independent judge or human annotation protocol. Omit unavailable fields rather
than estimating them. Create separate prediction files for ablations (for
example, `no_challenger.csv` and `no_verifier.csv`) and score them with the same
command and split.

`results/latest.json` is generated evidence. Do not hand-edit it.
