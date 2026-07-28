# Data card — `uci_audit_v1`

Real-label benchmark. Built by `scripts/build_uci_audit_benchmark.py` from a vendored copy
of the source archive; `--verify-only` proves the committed CSV is byte-identical to a
fresh build.

## Provenance

| | |
|---|---|
| Source | UCI Machine Learning Repository, dataset 475, "Audit Data" |
| URL | https://archive.ics.uci.edu/dataset/475/audit+data |
| Citation | Hooda, N., Bawa, S., & Rana, P. S. (2018). *Fraudulent Firm Classification: A Case Study of an External Audit.* Applied Artificial Intelligence, 32(1), 48–64. |
| Licence | CC BY 4.0 |
| Vendored archive | `datasets/raw/uci_audit_data_id475.zip` |
| Archive SHA-256 | `4d9f4dc4c398995505c88a903ce0b5e5c70516e5bcd6b3ba03c8f7a8db57a142` |
| Collection | Firms examined by a government external-audit office; monetary values in crore rupees |

**These are real audit outcomes, not simulated ones.** They are also not a general
fraud-detection corpus: they describe one audit office, one jurisdiction, one period. See
Limitations.

## What each record is

One firm, described at two stages that the archive keeps in separate files:

- `trial.csv` — the **pre-audit screen**. Its `Risk` column is the screening flag.
- `audit_risk.csv` — the **post-audit finding**. Its `Risk` column is the benchmark label.

The two stages are recorded for the same 776 firms in the same row order.

## The structural property this benchmark is built on

The screen's flags are strictly nested inside the findings:

| | finding = 0 | finding = 1 |
|---|---:|---:|
| **screen flag = 0** | 290 | **0** |
| **screen flag = 1** | 181 | 305 |

No firm the audit found risky was missed by the screen. So across the full dataset the
incumbent screen has **recall 1.000 and specificity 0.616**, and the 181 firms in the
flag=1 / finding=0 cell are *real* hard negatives — flagged by policy, then cleared by a
human auditor after examination.

The builder asserts this invariant and fails if it is ever violated. It is the reason this
dataset was chosen: it poses the operational question directly, on real labels. Improving
specificity without losing recall is the target; a method that simply flags everything
scores recall 1.000 and specificity 0.000 and is visibly useless in the tables.

## Fields

Retained as model input:

| Column | Meaning |
|---|---|
| `sector_score` | Historical risk score of the firm's sector |
| `location_id` | Location identifier |
| `para_a_discrepancy_cr` | Discrepancy reported in the planned-audit para (crore INR) |
| `para_b_discrepancy_cr` | Discrepancy reported in the unplanned-audit para (crore INR) |
| `total_discrepancy_cr` | Total across both paras |
| `discrepancy_count` | Number of distinct discrepancy findings |
| `money_value_cr` | Money value of misstatements found in prior audits |
| `district_loss_score` | District loss indicator |
| `history_score` | Historical discrepancy record |
| `prior_screen_flag` | Whether the pre-audit screen flagged the firm |
| `prior_screen_score` | The pre-audit screen's score |

Research-only, never shown to a predictor: `risk_label`, `risk_category`, `difficulty`,
`split`, `label_source`, `source_row_index`, `dataset_version`, `generator_version`.

## Leakage control

`audit_risk.csv` also ships the audit office's own scoring intermediates. `Risk` is a
threshold on `Audit_Risk`, which is computed from them, so every one of these is dropped:

```
Score_A  Risk_A  Score_B  Risk_B  Risk_C  Score_MV  Risk_D  PROB  RiSk_E
Prob  Risk_F  Score  Inherent_Risk  CONTROL_RISK  Detection_Risk  Audit_Risk
```

The builder asserts all 16 are present in the archive before dropping them, so a future
archive revision that renames or adds a derived column fails the build instead of silently
leaking. A test independently re-checks that none survive into the benchmark.

## Split

Content-addressed, not seeded: `sha256("skeptic-engine-uci-audit-v1:" + case_id)`, bucketed,
target evaluation fraction 0.45. No RNG state is involved, so the split is identical on any
checkout and cannot drift when rows are added or reordered.

| | Records | Positive | Negative |
|---|---:|---:|---:|
| Development | 430 | 159 | 271 |
| **Evaluation (frozen)** | **346** | **146** | **200** |
| — of which flagged by the screen | 212 | 146 | 66 |
| — of which real hard negatives | 66 | 0 | 66 |

Committed CSV SHA-256 is recorded in `uci_audit_v1.manifest.json` under `artifacts`.

## Descriptive slices

`risk_category` and `difficulty` are reporting slices only, computed from the data and never
used as model input. Two of them need a caveat:

- `cleared_after_flag` / `difficulty = hard` are, by definition, the flagged-then-cleared
  firms. The incumbent screen therefore scores **0.000 accuracy on that slice by
  construction** — it flagged all of them. That is not a bug in the slice; it is the whole
  point of the slice, and it is where any method that beats the screen must win.
- `not_flagged` firms are all true negatives, again by the nesting property.

Difficulty thresholds for the `borderline` band are computed on the **development split
only** and recorded in the manifest.

## Imputation

One firm has a blank `Money_Value` in the archive. It is imputed with the median of the
observed values; the value and the affected case ID are recorded in the manifest under
`imputation` rather than silently applied.

## Evidence corpus

`uci_audit_v1.evidence.json` holds 5,432 documents, seven per firm. Each is a deterministic
natural-language rendering of one recorded field — no fact is added. They exist so that
citation correctness is measurable and so the no-RAG ablation has something real to remove.

## Limitations

1. **Not generalisable.** One audit office, one jurisdiction, one period. Results here do not
   transfer to a different ledger, country, or fraud typology.
2. **The label is an audit *finding*, not a conviction.** It records what an external audit
   concluded, which is the right target for an audit-assistance system but is not the same as
   adjudicated fraud.
3. **A tabular model already does well.** A logistic regression fitted on the development
   split reaches 0.962 accuracy on the held-out set. Headroom for a reasoning system on raw
   accuracy is therefore small, and any claim of improvement must be made on specificity,
   groundedness or cost, with an interval attached.
4. **Small by modern standards.** 776 records, 346 held out. Bootstrap intervals are wide
   enough that small differences between methods will not be resolvable, and the tables
   report them so that this is visible rather than assumed away.
5. **No temporal split.** The archive carries no usable date field, so the split cannot test
   distribution shift over time.
6. **Monetary units** are crore rupees at the time of collection and are not inflation-adjusted.

## Intended and unintended use

Intended: benchmarking audit-triage methods, with the reported limitations attached.

Not intended: making decisions about any real firm or individual, training a deployed
screening system, or supporting any claim about fraud rates in a population.
