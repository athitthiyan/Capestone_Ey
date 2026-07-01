import { apiRequest } from "@/services/api";
import type { AppSettings } from "@/types/domain";

type ApiAppSettings = {
  reasoning_model: string;
  report_model: string;
  auto_clear_threshold: number;
  reviewer_threshold: number;
  materiality: number;
  segregation_of_duties: boolean;
  immutable_audit_log: boolean;
  debate_round_cap: number;
  api_key_vault: string;
  theme: AppSettings["theme"];
  display_currency: string;
  notifications: boolean;
  audit_retention_years: number;
  ip_allowlist: boolean;
  estimated_agent_run_cost_usd: number;
};

function mapSettings(settings: ApiAppSettings): AppSettings {
  return {
    reasoningModel: settings.reasoning_model,
    reportModel: settings.report_model,
    autoClearThreshold: settings.auto_clear_threshold,
    reviewerThreshold: settings.reviewer_threshold,
    materiality: settings.materiality,
    segregationOfDuties: settings.segregation_of_duties,
    immutableAuditLog: settings.immutable_audit_log,
    debateRoundCap: settings.debate_round_cap,
    apiKeyVault: settings.api_key_vault,
    theme: settings.theme,
    displayCurrency: settings.display_currency,
    notifications: settings.notifications,
    auditRetentionYears: settings.audit_retention_years,
    ipAllowlist: settings.ip_allowlist,
    estimatedAgentRunCostUsd: settings.estimated_agent_run_cost_usd,
  };
}

export async function getSettings(): Promise<AppSettings> {
  return mapSettings(await apiRequest<ApiAppSettings>("/settings"));
}
