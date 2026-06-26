import type { AppSettings } from "@/types/domain";

export const mockSettings: AppSettings = {
  reasoningModel: "gpt-5-enterprise-reasoning",
  reportModel: "gpt-5-enterprise-writing",
  autoClearThreshold: 0.9,
  reviewerThreshold: 0.78,
  materiality: 25000,
  segregationOfDuties: true,
  immutableAuditLog: true,
  debateRoundCap: 2,
  apiKeyVault: "Configured in secure vault",
  theme: "light",
  notifications: true,
  auditRetentionYears: 7,
  ipAllowlist: true,
};
