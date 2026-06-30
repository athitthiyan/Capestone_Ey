"use client";

import { BarChart3 } from "lucide-react";
import dynamic from "next/dynamic";
import { ChartSkeleton } from "@/components/shared/chart-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAgentAccuracy, useAnalyticsKpis, useAnalyticsTrend } from "@/hooks/use-analytics";

const AnalyticsCharts = dynamic(
  () => import("@/components/analytics/analytics-charts").then((m) => m.AnalyticsCharts),
  { ssr: false, loading: () => <ChartSkeleton className="h-80" /> },
);

export function AnalyticsView() {
  const trendQuery = useAnalyticsTrend();
  const accuracyQuery = useAgentAccuracy();
  const kpiQuery = useAnalyticsKpis();

  if (trendQuery.isLoading || accuracyQuery.isLoading || kpiQuery.isLoading) {
    return <LoadingState label="Loading analytics" />;
  }

  if (trendQuery.error || accuracyQuery.error || kpiQuery.error) {
    return <ErrorState onRetry={() => void Promise.all([trendQuery.refetch(), accuracyQuery.refetch(), kpiQuery.refetch()])} />;
  }

  const trend = trendQuery.data ?? [];
  const accuracy = accuracyQuery.data ?? [];
  const kpis = kpiQuery.data ?? [];
  const latestConfidence = trend.at(-1)?.confidence ?? 0;
  const latestVerifierRate = trend.at(-1)?.verifierRate ?? 0;
  const hasAnalytics = trend.length > 0 || accuracy.length > 0 || kpis.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Analytics"
        title="Investigation performance"
        description="Track AI assurance quality, verifier grounding rates, reviewer load, and confidence trends across the engagement."
        actions={
          <Button variant="secondary">
            <BarChart3 className="h-4 w-4" aria-hidden="true" />
            Export dashboard
          </Button>
        }
      />

      {hasAnalytics ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {kpis.map((metric) => (
              <Card key={metric.label}>
                <CardContent className="p-4">
                  <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{metric.label}</p>
                  <p className="mt-2 font-mono text-2xl text-foreground">{metric.value}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{metric.helper}</p>
                </CardContent>
              </Card>
            ))}
            <Card>
              <CardContent className="p-4">
                <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Latest confidence</p>
                <p className="mt-2 font-mono text-2xl text-foreground">{Math.round(latestConfidence * 100)}%</p>
                <p className="mt-1 text-xs text-muted-foreground">Verifier {Math.round(latestVerifierRate * 100)}%</p>
              </CardContent>
            </Card>
          </section>

          <AnalyticsCharts trend={trend} accuracy={accuracy} />
        </>
      ) : (
        <EmptyState
          title="No analytics data"
          description="Analytics will appear after the backend exposes evaluation or telemetry records."
          icon={BarChart3}
        />
      )}
    </div>
  );
}
