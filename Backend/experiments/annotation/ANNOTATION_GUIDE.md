# Annotation and adjudication guide

Annotators label synthetic **audit-risk indicators**, never confirmed fraud. Review the ledger
fields and supplied evidence independently; do not inspect model predictions from other methods.

- `risk_label=0`: no defined control anomaly. Legitimate high-value or manual entries remain
  normal when authorization and evidence are complete.
- `risk_label=1`: at least one defined control anomaly (materiality with missing authorization,
  related party, document gap, segregation-of-duty conflict, duplicate, or altered evidence).
- Borderline: evidence is ambiguous or amount lies near a control threshold; select the best
  label and lower confidence.
- Severity: 0 informational, 1 low, 2 medium, 3 high, 4 critical.
- Confidence: 0 to 1 probability that the selected rubric label is correct.
- Groundedness: 0 unsupported/contradicted, 0.5 partially supported, 1 fully supported.
- Citation correctness: 0 irrelevant/incorrect, 0.5 partial, 1 direct and sufficient.

Human mode requires at least two blinded reviewers. Model-assisted mode may draft a label, but a
human must accept or replace every field and identify the assistance in notes. Disagreements go
to a third qualified reviewer who sees the original evidence and both rationales. The final
adjudicated label and notes are append-only; reviewer rows are retained. Report percentage
agreement and Cohen's kappa for two reviewers, Fleiss' kappa for three or more, and weighted
kappa for ordinal scores. Never report agreement until real reviewer rows exist.

The schema is in `annotation_schema.csv`. Reviewer IDs must be pseudonymous. Notes must not
contain personal data, secrets, private prompts, or chain-of-thought.
