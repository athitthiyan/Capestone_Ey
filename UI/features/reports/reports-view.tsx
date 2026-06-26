"use client";

import { Download, FileText, Printer } from "lucide-react";
import Link from "next/link";
import { ReportPreview } from "@/components/reports/report-preview";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { routes } from "@/constants/routes";
import { useReports } from "@/hooks/use-reports";

export function ReportsView({ caseId }: { caseId: string }) {
  const { data, error, isLoading, refetch } = useReports();

  if (isLoading) {
    return <LoadingState label="Loading reports" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Report generation"
        title="Professional skepticism reports"
        description="Generate source-grounded memos and governance packs from verified claims, debate outcomes, reviewer decisions, and audit log evidence."
        actions={
          <>
            <Button asChild variant="secondary">
              <Link href={routes.caseWorkspace(caseId)}>
                <FileText className="h-4 w-4" aria-hidden="true" />
                Open active case
              </Link>
            </Button>
            <Button variant="secondary">
              <Printer className="h-4 w-4" aria-hidden="true" />
              Print preview
            </Button>
            <Button>
              <Download className="h-4 w-4" aria-hidden="true" />
              Export PDF
            </Button>
          </>
        }
      />

      <section className="grid gap-4">
        {data.map((report) => (
          <ReportPreview key={report.id} report={report} />
        ))}
      </section>
    </div>
  );
}
