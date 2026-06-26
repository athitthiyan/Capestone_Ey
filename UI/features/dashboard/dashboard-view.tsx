"use client";

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleDollarSign,
  Gauge,
  Plus,
  ReceiptText,
  ShieldAlert,
  TrendingUp,
  UserCheck,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { AgentHealthPanel } from "@/components/agents/agent-health-panel";
import { RiskDistribution } from "@/components/dashboard/risk-distribution";
import { ChartSkeleton } from "@/components/shared/chart-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { InvestigationsTable } from "@/components/investigations/investigations-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { routes } from "@/constants/routes";
import { useDashboardSummary } from "@/hooks/use-cases";
import { useAnalyticsTrend } from "@/hooks/use-analytics";

const metricIcons = [
  ReceiptText,
  ReceiptText,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  UserCheck,
  UserCheck,
  Gauge,
  Bot,
  CircleDollarSign,
] as const;

const CaseTrendChart = dynamic(
  () => import("@/components/dashboard/case-trend-chart").then((m) => m.CaseTrendChart),
  { ssr: false, loading: () => <ChartSkeleton className="h-72" /> },
);

export function DashboardView() {
  const { data, error, isLoading, refetch } = useDashboardSummary();
  const trendQuery = useAnalyticsTrend();

  if (isLoading) {
    return <LoadingState label="Loading dashboard" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Executive overview"
        title={`${data.engagement} / ${data.period}`}
        description="Monitor investigation throughput, agent health, risk distribution, and cases that require professional skepticism escalation."
        actions={
          <Button asChild>
            <Link href={routes.investigations}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              New investigation
            </Link>
          </Button>
        }
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Dashboard metrics">
        {data.metrics.map((metric, index) => (
          <StatCard key={metric.label} icon={metricIcons[index] ?? TrendingUp} {...metric} />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <RiskDistribution summary={data} />
        <AgentHealthPanel agents={data.agentHealth} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <CaseTrendChart trend={trendQuery.data ?? []} />
        <Card>
          <CardHeader>
            <CardTitle>API health and cost</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              ["Claude Sonnet", "operational", "2.4M tokens"],
              ["Claude Haiku", "operational", "1.7M tokens"],
              ["FX API", "credential pending", "$0.00"],
              ["Registry API", "cached", "84 lookups"],
            ].map(([label, status, usage]) => (
              <div key={label} className="flex items-center gap-3 rounded-md border border-border bg-muted/40 px-3 py-2">
                <span className="h-2 w-2 rounded-full bg-success" aria-hidden="true" />
                <span className="text-sm font-medium text-foreground">{label}</span>
                <span className="ml-auto text-xs text-muted-foreground">{status}</span>
                <span className="font-mono text-xs text-foreground">{usage}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground">Recent investigations</h2>
          <Button asChild variant="ghost" size="sm">
            <Link href={routes.investigations}>View all</Link>
          </Button>
        </div>
        <InvestigationsTable investigations={data.recentInvestigations} />
      </section>
    </div>
  );
}
