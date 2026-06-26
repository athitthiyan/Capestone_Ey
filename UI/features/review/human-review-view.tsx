"use client";

import { UserCheck } from "lucide-react";
import Link from "next/link";
import { HumanReviewPanel } from "@/components/review/human-review-panel";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { routes } from "@/constants/routes";
import { useReviewQueue } from "@/hooks/use-cases";
import { useDebateArguments } from "@/hooks/use-debate";
import { useInvestigation } from "@/hooks/use-investigation";
import { useReviewHistory } from "@/hooks/use-review";

export function HumanReviewView({ caseId }: { caseId: string }) {
  const investigationQuery = useInvestigation(caseId);
  const queueQuery = useReviewQueue();
  const historyQuery = useReviewHistory(caseId);
  const debateQuery = useDebateArguments(caseId);

  if (investigationQuery.isLoading || queueQuery.isLoading || historyQuery.isLoading || debateQuery.isLoading) {
    return <LoadingState label="Loading review queue" />;
  }

  if (investigationQuery.error || queueQuery.error || historyQuery.error || debateQuery.error) {
    return (
      <ErrorState
        onRetry={() =>
          void Promise.all([investigationQuery.refetch(), queueQuery.refetch(), historyQuery.refetch(), debateQuery.refetch()])
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Human review"
        title="Partner decision panel"
        description="Document reviewer judgement, capture rationale, and preserve the decision trail for high-risk AI-assisted conclusions."
        actions={
          <Button asChild variant="secondary">
            <Link href={routes.auditLogs}>
              <UserCheck className="h-4 w-4" aria-hidden="true" />
              View audit trail
            </Link>
          </Button>
        }
      />

      <HumanReviewPanel
        debate={debateQuery.data ?? []}
        history={historyQuery.data ?? []}
        investigation={investigationQuery.data}
        queue={queueQuery.data ?? []}
      />
    </div>
  );
}
