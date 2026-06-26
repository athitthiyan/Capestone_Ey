import type { AgentAccuracy, AnalyticsPoint } from "@/types/domain";

export const analyticsTrend: AnalyticsPoint[] = [
  { week: "May 18", confidence: 0.8, verifierRate: 0.72 },
  { week: "May 25", confidence: 0.82, verifierRate: 0.76 },
  { week: "Jun 01", confidence: 0.84, verifierRate: 0.79 },
  { week: "Jun 08", confidence: 0.83, verifierRate: 0.81 },
  { week: "Jun 15", confidence: 0.86, verifierRate: 0.84 },
  { week: "Jun 22", confidence: 0.88, verifierRate: 0.87 },
];

export const agentAccuracy: AgentAccuracy[] = [
  { agent: "Evidence", accuracy: 0.94 },
  { agent: "Challenger", accuracy: 0.89 },
  { agent: "Defender", accuracy: 0.86 },
  { agent: "Adjudicator", accuracy: 0.88 },
  { agent: "Verifier", accuracy: 0.92 },
];

export const analyticsKpis = [
  { label: "Multi-agent uplift", value: "24%", helper: "FP reduction vs single prompt", tone: "success" },
  { label: "False-positive reduction", value: "6.2%", helper: "-2.1 pts over baseline", tone: "success" },
  { label: "False-negative comparison", value: "1.8%", helper: "-0.6 pts over baseline", tone: "success" },
  { label: "Grounding rate", value: "92%", helper: "first-pass verifier success", tone: "success" },
  { label: "Hallucination catch rate", value: "8.4%", helper: "claims revised before report", tone: "warning" },
  { label: "Auto-clear rate", value: "59%", helper: "low-risk cases cleared", tone: "default" },
  { label: "Reviewer effort saved", value: "31h", helper: "estimated in last 30 days", tone: "success" },
  { label: "LLM cost / case", value: "$0.21", helper: "4.1M tokens total", tone: "warning" },
] as const;
