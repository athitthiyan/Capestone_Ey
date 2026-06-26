"use client";

import { FileSearch } from "lucide-react";
import { useMemo, useState } from "react";
import { EvidenceCard } from "@/components/evidence/evidence-card";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEvidence } from "@/hooks/use-evidence";
import type { EvidenceSource } from "@/types/domain";

const emptyEvidence: EvidenceSource[] = [];

export function EvidenceView({ caseId }: { caseId?: string }) {
  const { data, error, isLoading, refetch } = useEvidence(caseId);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<EvidenceSource["type"] | "all">("all");
  const [qualityFilter, setQualityFilter] = useState<EvidenceSource["quality"] | "all">("all");
  const evidence = data ?? emptyEvidence;
  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return evidence.filter((item) => {
      const matchesQuery =
        !normalizedQuery ||
        [item.title, item.summary, item.citation, item.type, ...item.tags].some((value) =>
          value.toLowerCase().includes(normalizedQuery),
        );
      const matchesType = typeFilter === "all" || item.type === typeFilter;
      const matchesQuality = qualityFilter === "all" || item.quality === qualityFilter;

      return matchesQuery && matchesType && matchesQuality;
    });
  }, [evidence, qualityFilter, query, typeFilter]);

  if (isLoading) {
    return <LoadingState label="Loading evidence" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Evidence explorer"
        title="Source-grounded evidence"
        description="Inspect citations, source versions, confidence scores, and linked cases before relying on an agent conclusion."
        actions={
          <Button variant="secondary">
            <FileSearch className="h-4 w-4" aria-hidden="true" />
            Source map
          </Button>
        }
      />

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-4" aria-label="Evidence filters">
        <div className="md:col-span-2">
          <label htmlFor="evidence-search" className="sr-only">
            Search evidence
          </label>
          <Input
            id="evidence-search"
            placeholder="Search evidence title, citation, or tag"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <label className="text-xs text-muted-foreground">
          Source type
          <select
            className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value as EvidenceSource["type"] | "all")}
          >
            <option value="all">All sources</option>
            <option value="Policy">Policy</option>
            <option value="History">History</option>
            <option value="Vendor">Vendor</option>
            <option value="External API">External API</option>
            <option value="Ledger">Ledger</option>
            <option value="Contract">Contract</option>
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Quality
          <select
            className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
            value={qualityFilter}
            onChange={(event) => setQualityFilter(event.target.value as EvidenceSource["quality"] | "all")}
          >
            <option value="all">All quality</option>
            <option value="strong">Strong</option>
            <option value="adequate">Adequate</option>
            <option value="weak">Weak</option>
            <option value="missing">Missing</option>
          </select>
        </label>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        {filtered.map((evidence) => (
          <EvidenceCard key={evidence.id} evidence={evidence} />
        ))}
      </section>
    </div>
  );
}
