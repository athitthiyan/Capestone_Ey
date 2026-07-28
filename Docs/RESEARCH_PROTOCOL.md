# Research protocol

> Does adversarial multi-agent reasoning with retrieval and verification improve anomaly-detection
> precision, specificity, evidential groundedness, and citation correctness over deterministic
> rules and a single-LLM baseline?

All methods use benchmark v1's frozen evaluation IDs. Labels and research metadata are hidden
from methods. Tests are two-sided at alpha 0.05 with bootstrap 95% CIs; effect sizes and practical
importance take precedence over isolated p-values. McNemar tests require paired binary outputs;
permutation tests are used for continuous paired quality differences when exchangeability is
reasonable. Holm correction will be applied when multiple confirmatory comparisons are executed.

| Hypothesis | Independent variable | Dependent variables | Baseline | Test and acceptance criterion | Confounders |
|---|---|---|---|---|---|
| H1 multi-agent improves specificity | Method | Specificity, FPR | Rules | McNemar; CI for specificity difference excludes 0 and improvement >0 | Model/provider, threshold |
| H2 Verifier improves evidence quality | Verifier enabled | Groundedness, citation correctness | No Verifier | Paired permutation/bootstrap; positive CI and reviewed rubric | Judge bias, retrieval |
| H3 RAG reduces unsupported conclusions | Retrieval enabled | Unsupported-claim rate, groundedness | No RAG | Paired permutation; groundedness improves and unsupported rate falls | Corpus quality |
| H4 debate helps but costs more | Debate rounds/roles | Hard-case F1, latency, cost | No Challenger / one round | McNemar plus bootstrap latency/cost; quality gain with reported trade-off | Prompt length, caching |
| H5 crew beats single LLM on difficult cases | Method | Hard-negative specificity, hard-positive recall, F1 | Single LLM | Paired McNemar and bootstrap effect | Difficulty generator artifacts |
| H6 calibration reduces unsafe clearance | Calibration/threshold | Brier, ECE, false-clear rate | Uncalibrated confidence | Held-out calibration improves ECE and does not increase false-clear rate | Prevalence shift |

The development split may be used for prompts/rules. The evaluation split is opened only for
final scoring. Human annotation requires blinded independent review and adjudication. Synthetic
labels are audit-risk proxies, not fraud. See `Backend/experiments/configs`, the annotation guide,
and `EXPERIMENT_REPRODUCTION.md`.
