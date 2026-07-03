import { apiRequest } from "@/services/api";
import { type ApiAuditEvent, mapAuditEvent } from "@/services/audit.service";
import { type ApiInvestigation, mapInvestigation } from "@/services/cases.service";
import { type ApiDebateMessage, mapDebateMessage } from "@/services/debate.service";
import {
  type ApiEvidenceVerification,
  mapEvidenceVerification,
} from "@/services/evidence-verification.service";
import { type ApiEvidence, mapEvidence } from "@/services/evidence.service";
import { type ApiEvaluationSummary, mapEvaluation } from "@/services/evaluation.service";
import { type ApiReport, mapReport } from "@/services/reports.service";
import { type ApiVerificationClaim, mapVerificationClaim } from "@/services/verification.service";
import type {
  AuditEvent,
  DebateArgument,
  EvaluationSummary,
  EvidenceSource,
  EvidenceVerification,
  Investigation,
  ReportArtifact,
  VerificationClaim,
} from "@/types/domain";

type ApiInvestigationWorkspace = {
  investigation: ApiInvestigation;
  evidence: ApiEvidence[];
  debate: ApiDebateMessage[];
  verification: ApiVerificationClaim[];
  evidence_verification?: ApiEvidenceVerification | null;
  audit: ApiAuditEvent[];
  reports: ApiReport[];
  evaluation: ApiEvaluationSummary;
};

export type InvestigationWorkspace = {
  investigation: Investigation;
  evidence: EvidenceSource[];
  debate: DebateArgument[];
  verification: VerificationClaim[];
  evidenceVerification: EvidenceVerification | null;
  auditEvents: AuditEvent[];
  reports: ReportArtifact[];
  evaluation: EvaluationSummary;
};

export async function getInvestigationWorkspace(caseId: string): Promise<InvestigationWorkspace> {
  const payload = await apiRequest<ApiInvestigationWorkspace>(
    `/investigations/${encodeURIComponent(caseId)}/workspace`,
  );

  return {
    investigation: mapInvestigation(payload.investigation),
    evidence: payload.evidence.map((row) => mapEvidence(row, caseId)),
    debate: payload.debate.map(mapDebateMessage),
    verification: payload.verification.map(mapVerificationClaim),
    evidenceVerification: payload.evidence_verification
      ? mapEvidenceVerification(payload.evidence_verification)
      : null,
    auditEvents: payload.audit.map((row) => mapAuditEvent(row, caseId)),
    reports: payload.reports.map(mapReport),
    evaluation: mapEvaluation(payload.evaluation),
  };
}
