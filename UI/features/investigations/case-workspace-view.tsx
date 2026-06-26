"use client";

import { ExternalLink, FileSearch, Play } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { AuditTimeline } from "@/components/audit/audit-timeline";
import { DebateMessage } from "@/components/debate/debate-message";
import { EvidenceCard } from "@/components/evidence/evidence-card";
import { ReportPreview } from "@/components/reports/report-preview";
import { ChartSkeleton } from "@/components/shared/chart-skeleton";
import { ConfidenceMeter } from "@/components/shared/confidence-meter";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { RiskBadge } from "@/components/shared/risk-badge";
import { WorkflowStatusBadge } from "@/components/shared/status-badge";
import { VerificationClaimCard } from "@/components/verification/verification-claim-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { routes } from "@/constants/routes";
import { useAgentWorkflow } from "@/hooks/use-agent-workflow";
import { useAuditEvents } from "@/hooks/use-audit-events";
import { useDebateArguments } from "@/hooks/use-debate";
import { useEvidence } from "@/hooks/use-evidence";
import { useInvestigation } from "@/hooks/use-investigation";
import { useReports } from "@/hooks/use-reports";
import { useVerificationClaims } from "@/hooks/use-verification";
import { formatCurrency } from "@/lib/utils";

const AgentWorkflow = dynamic(
  () => import("@/components/agents/agent-workflow").then((m) => m.AgentWorkflow),
  { ssr: false, loading: () => <ChartSkeleton className="h-[520px]" /> },
);

export function CaseWorkspaceView({ caseId }: { caseId: string }) {
  const investigationQuery = useInvestigation(caseId);
  const workflowQuery = useAgentWorkflow();
  const evidenceQuery = useEvidence(caseId);
  const debateQuery = useDebateArguments(caseId);
  const verificationQuery = useVerificationClaims(caseId);
  const reportsQuery = useReports();
  const auditQuery = useAuditEvents(caseId);

  if (investigationQuery.isLoading || workflowQuery.isLoading || evidenceQuery.isLoading) {
    return <LoadingState label="Loading case workspace" />;
  }

  if (investigationQuery.error || workflowQuery.error || evidenceQuery.error) {
    return <ErrorState onRetry={() => void Promise.all([investigationQuery.refetch(), workflowQuery.refetch(), evidenceQuery.refetch()])} />;
  }

  const investigation = investigationQuery.data;

  if (!investigation) {
    return (
      <EmptyState
        title="Case not found"
        description="The selected investigation does not exist in the current engagement workspace."
        icon={FileSearch}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investigation workspace"
        title={`${investigation.id} / ${investigation.vendor}`}
        description={investigation.description}
        actions={
          <>
            <Button asChild variant="secondary">
              <Link href={routes.replay}>
                <Play className="h-4 w-4" aria-hidden="true" />
                Replay
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href={routes.evidence}>
                <FileSearch className="h-4 w-4" aria-hidden="true" />
                Evidence
              </Link>
            </Button>
            <Button asChild>
              <Link href={routes.review}>
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
                Review
              </Link>
            </Button>
          </>
        }
      />

      <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Agent workflow</CardTitle>
          </CardHeader>
          <CardContent>
            <AgentWorkflow steps={workflowQuery.data ?? []} />
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Case facts</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Risk</span>
                <RiskBadge risk={investigation.risk} />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Status</span>
                <WorkflowStatusBadge status={investigation.status} />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Amount</span>
                <span className="font-mono text-foreground">{formatCurrency(investigation.amount)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Materiality</span>
                <span className="font-mono text-foreground">{formatCurrency(investigation.materiality)}</span>
              </div>
              <ConfidenceMeter value={investigation.confidence} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Open flags</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {investigation.flags.map((flag) => (
                <div key={flag} className="rounded-md border border-border bg-background px-3 py-2 text-sm text-muted-foreground">
                  {flag}
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Human review status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">Reviewer</span>
                <span className="text-sm font-medium text-foreground">{investigation.reviewer ?? "Unassigned"}</span>
              </div>
              <div className="rounded-md border border-warning-border bg-warning-soft px-3 py-2 text-sm text-warning-foreground">
                Awaiting partner decision and digital signature.
              </div>
              <Button asChild variant="secondary" className="w-full">
                <Link href={routes.review}>Open review bundle</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-foreground">Evidence attached to this case</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          {(evidenceQuery.data ?? []).map((evidence) => (
            <EvidenceCard key={evidence.id} evidence={evidence} />
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">Debate panel</h2>
          <div className="space-y-3">
            {(debateQuery.data ?? []).slice(0, 2).map((argument) => (
              <DebateMessage key={argument.id} argument={argument} />
            ))}
            <Button asChild variant="ghost" size="sm">
              <Link href={routes.debate}>Open full debate</Link>
            </Button>
          </div>
        </div>

        <div className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">Verification panel</h2>
          <div className="space-y-3">
            {(verificationQuery.data ?? []).slice(0, 2).map((claim) => (
              <VerificationClaimCard key={claim.id} claim={claim} />
            ))}
            <Button asChild variant="ghost" size="sm">
              <Link href={routes.verification}>Open verifier</Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">Report preview</h2>
          {reportsQuery.data?.[0] ? <ReportPreview report={reportsQuery.data[0]} /> : null}
        </div>
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-foreground">Audit trail</h2>
          <AuditTimeline events={(auditQuery.data ?? []).slice(0, 3)} />
        </div>
      </section>
    </div>
  );
}
