"use client";

import { CheckCircle2, FileDown, RefreshCw } from "lucide-react";
import { EvaluationComparison } from "@/components/evaluation/evaluation-comparison";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useEvaluationSummary } from "@/hooks/use-evaluation";

export function EvaluationView() {
  const { data, error, isLoading, refetch } = useEvaluationSummary();

  if (isLoading) {
    return <LoadingState label="Loading evaluation" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="A/B evaluation"
        title="Multi-agent crew vs single-prompt"
        description={`Benchmarked over ${data.cases} labelled cases - proving the multi-agent uplift (PRD G2) rather than asserting it.`}
        actions={
          <>
            <Button variant="secondary">
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Re-run eval
            </Button>
            <Button>
              <FileDown className="h-4 w-4" aria-hidden="true" />
              Export results
            </Button>
          </>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data.kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{kpi.label}</p>
                {kpi.pass ? (
                  <CheckCircle2 className="h-4 w-4 text-success-foreground" aria-hidden="true" />
                ) : null}
              </div>
              <p className="mt-2 font-mono text-2xl text-foreground">{kpi.value}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {kpi.helper} - target {kpi.target}
              </p>
            </CardContent>
          </Card>
        ))}
      </section>

      <EvaluationComparison comparison={data.comparison} hallucination={data.hallucination} />

      <Card className="border-l-4 border-l-primary">
        <CardContent className="p-4">
          <p className="text-sm font-semibold text-primary">Conclusion - each agent earns its place</p>
          <p className="mt-1 text-sm text-muted-foreground">{data.conclusion}</p>
        </CardContent>
      </Card>
    </div>
  );
}
