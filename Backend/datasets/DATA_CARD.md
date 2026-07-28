# GL Guardian Synthetic Benchmark v1

This privacy-safe dataset evaluates **audit-risk anomaly proxies**, not real fraud.

- Generator: `scripts/generate_benchmark_dataset.py`
- Version: 1.0.0
- Seed: 20260728
- Size: 600 transactions; exactly 300 positive and 300 negative labels
- License: repository MIT license; generated records contain no real people, customers, or transactions
- Split: deterministic SHA-256 assignment stored in `split`; approximately 80% development and 20% evaluation

## Schema and labels

Ledger fields describe amount, currency, documents, approval identities, payment method,
related-party status, and duplicate linkage. Research-only fields are `risk_label`,
`risk_category`, `difficulty`, `split`, and `generator_version`. Methods must never receive
`risk_label`, `risk_category`, `difficulty`, or `split` as input features.

Positive categories are materiality, related party, document gap, segregation of duties,
duplicate, borderline, and hard positive. Negative cases include ordinary transactions and
hard negatives such as legitimate high-value manual journals. Hard positives include
low-value anomalies. These deterministic labels encode the generator rubric and are not
independent professional judgments.

## Limitations and ethics

The benchmark tests controlled scenario coverage, not deployment prevalence or real-world
fraud performance. Synthetic patterns may reward rule matching, omit intersectional harms,
and underrepresent changing business controls. It must not justify accusations, automatic
discipline, payment holds, or autonomous audit conclusions. Qualified auditors must review
material decisions.

Regenerate from `Backend/` with:

```bash
python scripts/generate_benchmark_dataset.py
```

The adjacent manifest records the SHA-256 digest and distributions.
