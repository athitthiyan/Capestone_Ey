"use client";

import { ArrowRight, FileSpreadsheet, History, Info, Play, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { FlaggedRowsTable } from "@/components/intake/flagged-rows-table";
import { RulePrefilter } from "@/components/intake/rule-prefilter";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { routes } from "@/constants/routes";
import { useIntakeSummary } from "@/hooks/use-intake";
import { parseLedgerFile } from "@/services/intake.service";
import type { IntakeSummary } from "@/types/domain";

export function IntakeView() {
  const { data, error, isLoading, refetch } = useIntakeSummary();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadedSummary, setUploadedSummary] = useState<IntakeSummary | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [showPastRuns, setShowPastRuns] = useState(false);
  const [runStatus, setRunStatus] = useState("Sample pre-filter run loaded.");

  async function handleFile(file?: File) {
    if (!file) {
      return;
    }

    if (!/\.(csv|tsv)$/i.test(file.name)) {
      setUploadError("Upload a CSV or TSV ledger extract.");
      return;
    }

    setIsParsing(true);
    setUploadError(null);

    try {
      const parsed = await parseLedgerFile(file);
      setUploadedSummary(parsed);
      setRunStatus(`Parsed ${parsed.fileName}; ${parsed.flagged} rows flagged for case creation.`);
    } catch (parseError) {
      setUploadError(parseError instanceof Error ? parseError.message : "Unable to parse the uploaded file.");
    } finally {
      setIsParsing(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading intake run" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  const summary = uploadedSummary ?? data;
  const intakeRuns = uploadedSummary ? [data, uploadedSummary] : [data];
  const stats = [
    {
      label: "Rows ingested",
      value: summary.rowsIngested.toLocaleString(),
      helper: `${summary.parseErrors} parse errors`,
      tone: "text-foreground",
    },
    { label: "Flagged -> cases", value: summary.flagged.toLocaleString(), helper: "enter the crew", tone: "text-primary" },
    {
      label: "Cleared at intake",
      value: summary.cleared.toLocaleString(),
      helper: "dropped - no case",
      tone: "text-success-foreground",
    },
    {
      label: "Est. crew cost",
      value: `$${summary.estCostUsd}`,
      helper: `${summary.flagged} x $0.21`,
      tone: "text-foreground",
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Phase 0 - Case intake"
        title="GL ingestion & rule pre-filter"
        description="Ingest a general-ledger extract, normalize each row, and run the deterministic pre-filter. Only flagged rows become investigation cases; clean rows are cleared at intake."
        actions={
          <>
            <Button variant="secondary" onClick={() => setShowPastRuns((open) => !open)}>
              <History className="h-4 w-4" aria-hidden="true" />
              Past runs
            </Button>
            <Button asChild>
              <Link href={routes.investigations}>
                <Play className="h-4 w-4" aria-hidden="true" />
                Create cases &amp; run crew
              </Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardContent className="space-y-3 p-4">
            <p className="text-sm font-semibold text-foreground">GL data feed</p>
            <input
              ref={inputRef}
              className="sr-only"
              type="file"
              accept=".csv,.tsv,text/csv,text/tab-separated-values"
              aria-label="Upload general ledger CSV or TSV file"
              onChange={(event) => void handleFile(event.target.files?.[0])}
            />
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-lg border border-dashed border-border bg-background/60 p-4 text-left transition-colors hover:border-primary-border hover:bg-primary-soft/40"
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => {
                event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                void handleFile(event.dataTransfer.files[0]);
              }}
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-success-border bg-success-soft text-success-foreground">
                <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{summary.fileName}</p>
                <p className="font-mono text-xs text-muted-foreground">
                  {summary.rowsIngested.toLocaleString()} rows - {summary.columns.length} columns
                </p>
              </div>
              <Badge variant={uploadedSummary ? "primary" : "success"}>{uploadedSummary ? "uploaded" : "sample"}</Badge>
            </button>
            {uploadError ? <p className="text-xs text-danger-foreground">{uploadError}</p> : null}
            <p className="font-mono text-xs text-muted-foreground">{summary.columns.join(" - ")}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" size="sm" onClick={() => inputRef.current?.click()} disabled={isParsing}>
                <UploadCloud className="h-4 w-4" aria-hidden="true" />
                {isParsing ? "Parsing..." : "Replace file"}
              </Button>
              <Button
                size="sm"
                onClick={() => setRunStatus(`Pre-filter completed for ${summary.fileName}; ${summary.flagged} cases ready.`)}
              >
                Run pre-filter
              </Button>
              {uploadedSummary ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setUploadedSummary(null);
                    setRunStatus("Sample pre-filter run loaded.");
                  }}
                >
                  Reset sample
                </Button>
              ) : null}
            </div>
            <p className="rounded-md border border-info-border bg-info-soft px-3 py-2 text-xs text-info-foreground">{runStatus}</p>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          {stats.map((stat) => (
            <Card key={stat.label}>
              <CardContent className="p-4">
                <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">{stat.label}</p>
                <p className={`mt-2 font-mono text-2xl ${stat.tone}`}>{stat.value}</p>
                <p className="mt-1 text-xs text-muted-foreground">{stat.helper}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {showPastRuns ? (
        <Card>
          <CardContent className="space-y-3 p-4">
            <p className="text-sm font-semibold text-foreground">Past intake runs</p>
            {intakeRuns.map((run) => (
              <div
                key={`${run.fileName}-${run.flagged}`}
                className="flex flex-col gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm sm:flex-row sm:items-center"
              >
                <span className="font-medium text-foreground">{run.fileName}</span>
                <span className="text-muted-foreground">{run.rowsIngested.toLocaleString()} rows</span>
                <span className="text-primary">{run.flagged} flagged</span>
                <span className="text-success-foreground">{run.cleared} cleared</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1fr_1.3fr]">
        <RulePrefilter rules={summary.ruleStats} />
        <FlaggedRowsTable rows={summary.flaggedRows} />
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 p-4 text-sm text-muted-foreground md:flex-row md:items-center">
          <Info className="h-4 w-4 shrink-0 text-info-foreground" aria-hidden="true" />
          <span className="flex-1">
            {summary.cleared.toLocaleString()} clean rows were recorded as cleared-at-intake and never reach the agent
            crew - keeping the expensive debate off ~90% of the ledger.
          </span>
          <Button asChild className="shrink-0">
            <Link href={routes.investigations}>
              Create {summary.flagged} cases <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
