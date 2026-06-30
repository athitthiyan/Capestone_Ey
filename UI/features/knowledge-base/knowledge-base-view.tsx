"use client";

import { BookOpen } from "lucide-react";
import { useMemo, useState } from "react";
import { KnowledgeSourceCard } from "@/components/knowledge-base/knowledge-source-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useKnowledgeSources } from "@/hooks/use-knowledge";
import type { KnowledgeSource } from "@/types/domain";

const emptySources: KnowledgeSource[] = [];

export function KnowledgeBaseView() {
  const { data, error, isLoading, refetch } = useKnowledgeSources();
  const [query, setQuery] = useState("");
  const sources = data ?? emptySources;
  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return sources.filter(
      (source) =>
        !normalizedQuery ||
        [source.title, source.description, source.owner, source.clausePreview, ...source.citationIds].some((value) =>
          value.toLowerCase().includes(normalizedQuery),
        ),
    );
  }, [query, sources]);

  if (isLoading) {
    return <LoadingState label="Loading knowledge base" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Knowledge base"
        title="Governed source library"
        description="Maintain audit methodology, client policies, evidence connectors, and registry integrations used by the agent workflow."
        actions={
          <>
            <Button variant="secondary">
              <BookOpen className="h-4 w-4" aria-hidden="true" />
              Re-index
            </Button>
            <Button>Upload policy</Button>
          </>
        }
      />

      <div className="max-w-md">
        <label htmlFor="knowledge-search" className="sr-only">
          Search knowledge sources
        </label>
        <Input
          id="knowledge-search"
          placeholder="Search policies, clauses, citations, or owners"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      <section className="grid gap-4 lg:grid-cols-2">
        {filtered.map((source) => (
          <KnowledgeSourceCard key={source.id} source={source} />
        ))}
      </section>

      {filtered.length === 0 ? (
        <EmptyState
          title="No knowledge sources"
          description="Knowledge sources will appear after policy or connector records are available from the backend."
          icon={BookOpen}
        />
      ) : null}
    </div>
  );
}
