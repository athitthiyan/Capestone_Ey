import type { EvaluationSummary } from "@/types/domain";

export const mockEvaluationSummary: EvaluationSummary = {
  cases: 50,
  kpis: [
    { label: "FP reduction", value: "-22%", helper: "vs single-prompt", target: ">= 20%", pass: true },
    { label: "Hallucination catch", value: "84%", helper: "seeded ungrounded claims", target: ">= 80%", pass: true },
    { label: "Grounding rate", value: "96%", helper: "first/second-pass verifier", target: ">= 95%", pass: true },
    { label: "Auto-clear rate", value: "42%", helper: "low-risk cases cleared", target: "30–50%", pass: true },
  ],
  comparison: [
    { metric: "False-positive rate", singlePrompt: "28%", crew: "6.2%", delta: "-22 pts", better: true },
    { metric: "False-negative rate", singlePrompt: "2.4%", crew: "1.8%", delta: "-0.6 pts", better: true },
    { metric: "Grounded citations", singlePrompt: "-", crew: "96%", delta: "+96", better: true },
    { metric: "Hallucination catch", singlePrompt: "0%", crew: "84%", delta: "+84", better: true },
    { metric: "Cost / case", singlePrompt: "$0.05", crew: "$0.21", delta: "+$0.16", better: false },
  ],
  hallucination: [
    { label: "Caught -> revised", count: 21, total: 25, tone: "success" },
    { label: "Missed", count: 4, total: 25, tone: "danger" },
  ],
  conclusion:
    "The crew reduces false positives by 22 points and catches 84% of injected hallucinations the single pass misses. Ablation: removing the Defender raises FP by 11 pts; removing the Verifier drops hallucination-catch to 0 - each agent earns its place.",
};
