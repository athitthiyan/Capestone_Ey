"use client";

import { MessagesSquare } from "lucide-react";
import Link from "next/link";
import { DebateMessage } from "@/components/debate/debate-message";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { routes } from "@/constants/routes";
import { useDebateArguments } from "@/hooks/use-debate";

export function DebateView({ caseId }: { caseId: string }) {
  const { data, error, isLoading, refetch } = useDebateArguments(caseId);

  if (isLoading) {
    return <LoadingState label="Loading debate" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  const challengerArguments = data.filter((argument) => argument.side === "challenger");
  const defenderArguments = data.filter((argument) => argument.side === "defender");
  const adjudicatorArguments = data.filter((argument) => argument.side === "adjudicator");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Agent debate"
        title="Challenger and defender exchange"
        description="Review adversarial arguments, cited objections, defense claims, and the unresolved assertions that should drive human review."
        actions={
          <Button asChild variant="secondary">
            <Link href={routes.caseWorkspace(caseId)}>
              <MessagesSquare className="h-4 w-4" aria-hidden="true" />
              Open workspace
            </Link>
          </Button>
        }
      />

      <section className="grid gap-4 xl:grid-cols-[1fr_180px_1fr]">
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-danger-foreground">Challenger view</h2>
          {challengerArguments.map((argument) => (
            <DebateMessage key={argument.id} argument={argument} />
          ))}
        </div>
        <div className="space-y-4">
          <h2 className="text-center text-sm font-semibold text-primary">Adjudicator</h2>
          {adjudicatorArguments.map((argument) => (
            <DebateMessage key={argument.id} argument={argument} />
          ))}
        </div>
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-success-foreground">Defender view</h2>
          {defenderArguments.map((argument) => (
            <DebateMessage key={argument.id} argument={argument} />
          ))}
        </div>
      </section>

      <Card>
        <CardContent className="p-4">
          <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Debate transcript</p>
          <div className="mt-4 space-y-2">
            {data.map((argument) => (
              <div key={`${argument.id}-transcript`} className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
                <span className="font-medium text-foreground">{argument.side}</span>
                <span className="mx-2 text-muted-foreground">/</span>
                <span className="text-muted-foreground">{argument.summary}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
