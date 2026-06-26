export type RiskLevel = "critical" | "high" | "medium" | "low" | "cleared";

export type WorkState =
  | "done"
  | "running"
  | "queued"
  | "idle"
  | "challenger"
  | "review"
  | "blocked"
  | "failed"
  | "retry"
  | "escalated";

export type AgentRole =
  | "Supervisor"
  | "Evidence agent"
  | "Challenger"
  | "Defender"
  | "Adjudicator"
  | "Verifier"
  | "Confidence gate"
  | "Human review";

export type InvestigationStatus =
  | "intake"
  | "collecting_evidence"
  | "agent_debate"
  | "verification"
  | "human_review"
  | "report_ready"
  | "closed";

export type Investigation = {
  id: string;
  transactionId: string;
  vendor: string;
  category: string;
  amount: number;
  confidence: number;
  risk: RiskLevel;
  flags: string[];
  status: InvestigationStatus;
  owner: string;
  reviewer?: string;
  postedAt: string;
  dueAt: string;
  materiality: number;
  description: string;
};

export type Metric = {
  label: string;
  value: string;
  helper: string;
  tone?: "default" | "success" | "warning" | "danger";
};

export type RiskDistributionItem = {
  label: RiskLevel;
  count: number;
  percent: number;
};

export type AgentHealth = {
  label: AgentRole | "Evidence" | "Verifier";
  state: WorkState;
  latency: string;
  load: number;
};

export type DashboardSummary = {
  engagement: string;
  period: string;
  metrics: Metric[];
  riskDistribution: RiskDistributionItem[];
  throughput: {
    autoCleared: number;
    inReview: number;
    manual: number;
  };
  agentHealth: AgentHealth[];
  recentInvestigations: Investigation[];
};

export type PipelineStep = {
  id: string;
  role: AgentRole | "Report" | "Audit log";
  state: WorkState;
  detail: string;
  latency?: string;
  confidence?: number;
  tokenUsage: number;
  cost: number;
  attempt: number;
  expandedDetail: string;
};

export type EvidenceSource = {
  id: string;
  title: string;
  type: "Policy" | "History" | "Vendor" | "External API" | "Contract" | "Ledger";
  citation: string;
  summary: string;
  version: string;
  confidence: number;
  owner: string;
  lastVerified: string;
  linkedCases: string[];
  tags: string[];
  quality: "strong" | "adequate" | "weak" | "missing";
  preview: string;
};

export type DebateArgument = {
  id: string;
  side: "challenger" | "defender" | "adjudicator";
  title: string;
  timestamp: string;
  summary: string;
  tags: string[];
  footer: string;
  scoreLabel: string;
  citations: string[];
  confidence: number;
  details: string;
};

export type VerificationClaim = {
  id: string;
  claim: string;
  citation: string;
  status: "grounded" | "unsupported" | "missing";
  confidence: number;
  owner: string;
  supportingEvidence: string;
  notes: string;
  pass: "first_pass" | "second_pass" | "failed";
  action: "proceed" | "retry" | "revise";
};

export type ReplayStep = {
  id: string;
  title: string;
  detail: string;
  timestamp: string;
  state: WorkState;
};

export type AuditEvent = ReplayStep & {
  actor: string;
  caseId: string;
  hash: string;
  eventType: "agent" | "human" | "system" | "source";
  sourceRef: string;
};

export type ReportArtifact = {
  id: string;
  title: string;
  status: "draft" | "ready" | "approved";
  updatedAt: string;
  confidence: number;
  audience: "Engagement team" | "Partner" | "Audit committee";
  sections: string[];
  riskVerdict: RiskLevel;
  executiveSummary: string;
  humanDecision: string;
  reviewerSignature: string;
};

export type KnowledgeSource = {
  id: string;
  title: string;
  description: string;
  owner: string;
  count: string;
  freshness: string;
  status: "synced" | "review_needed" | "stale";
  clausePreview: string;
  versionHistory: string[];
  citationIds: string[];
  embeddingStatus: "indexed" | "indexing" | "failed";
};

export type AnalyticsPoint = {
  week: string;
  confidence: number;
  verifierRate: number;
};

export type AgentAccuracy = {
  agent: string;
  accuracy: number;
};

export type AnalyticsKpi = {
  label: string;
  value: string;
  helper: string;
  tone?: "default" | "success" | "warning" | "danger";
};

export type ReviewQueueItem = {
  id: string;
  caseId: string;
  title: string;
  risk: RiskLevel;
  confidence: number;
  dueAt: string;
  queue: "reviewer" | "partner";
};

export type ReviewHistoryItem = {
  id: string;
  actor: string;
  action: "approved" | "rejected" | "requested_evidence" | "escalated" | "resumed";
  comment: string;
  timestamp: string;
  signature: string;
};

export type ReplayFrame = {
  id: string;
  title: string;
  agent: string;
  timestamp: string;
  state: WorkState;
  prompt: string;
  input: string;
  output: string;
  citations: string[];
  tokenUsage: number;
  cost: number;
};

export type AppSettings = {
  reasoningModel: string;
  reportModel: string;
  autoClearThreshold: number;
  reviewerThreshold: number;
  materiality: number;
  segregationOfDuties: boolean;
  immutableAuditLog: boolean;
  debateRoundCap: number;
  apiKeyVault: string;
  theme: "system" | "light" | "dark";
  notifications: boolean;
  auditRetentionYears: number;
  ipAllowlist: boolean;
};

// --- Case intake (Phase 0): CSV ingestion + rule pre-filter ---
export type IntakeRuleStat = {
  rule: string;
  count: number;
  tone: "danger" | "warning" | "info";
};

export type FlaggedRow = {
  txnId: string;
  vendor: string;
  account: string;
  amount: string;
  rules: string[];
};

export type IntakeSummary = {
  fileName: string;
  rowsIngested: number;
  flagged: number;
  cleared: number;
  parseErrors: number;
  estCostUsd: number;
  columns: string[];
  ruleStats: IntakeRuleStat[];
  flaggedRows: FlaggedRow[];
};

// --- A/B evaluation: multi-agent crew vs single-prompt baseline ---
export type EvaluationKpi = {
  label: string;
  value: string;
  helper: string;
  target: string;
  pass: boolean;
};

export type EvaluationComparisonRow = {
  metric: string;
  singlePrompt: string;
  crew: string;
  delta: string;
  better: boolean;
};

export type HallucinationResult = {
  label: string;
  count: number;
  total: number;
  tone: "success" | "danger";
};

export type EvaluationSummary = {
  cases: number;
  kpis: EvaluationKpi[];
  comparison: EvaluationComparisonRow[];
  hallucination: HallucinationResult[];
  conclusion: string;
};
