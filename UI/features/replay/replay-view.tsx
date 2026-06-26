"use client";

import { LockKeyhole } from "lucide-react";
import { useState } from "react";
import { ReplayControls } from "@/components/replay/replay-controls";
import { StatusBadge } from "@/components/shared/status-badge";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useReplayFrames } from "@/hooks/use-replay";

export function ReplayView({ caseId }: { caseId: string }) {
  const { data, error, isLoading, refetch } = useReplayFrames(caseId);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [activeIndex, setActiveIndex] = useState(0);
  const frames = data ?? [];
  const activeFrame = frames[activeIndex];

  if (isLoading) {
    return <LoadingState label="Loading replay" />;
  }

  if (error || !data || !activeFrame) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Investigation replay"
        title={`${caseId} agent playback`}
        description="Step through prompt, input, output, citations, tokens, and cost for each agent action in the immutable investigation sequence."
        actions={
          <Badge variant="primary">
            <LockKeyhole className="mr-1 h-3 w-3" aria-hidden="true" />
            Immutable audit log
          </Badge>
        }
      />

      <ReplayControls
        playing={playing}
        speed={speed}
        onPlayingChange={setPlaying}
        onSpeedChange={setSpeed}
        onStepBack={() => setActiveIndex((value) => Math.max(value - 1, 0))}
        onStepForward={() => setActiveIndex((value) => Math.min(value + 1, frames.length - 1))}
      />

      <section className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="space-y-2">
          {frames.map((frame, index) => (
            <button
              key={frame.id}
              type="button"
              className="w-full rounded-lg border border-border bg-card p-3 text-left hover:bg-muted"
              aria-current={index === activeIndex ? "step" : undefined}
              onClick={() => setActiveIndex(index)}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-foreground">{frame.title}</span>
                <StatusBadge state={frame.state} />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {frame.agent} / {frame.timestamp}
              </p>
            </button>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{activeFrame.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 text-xs text-muted-foreground sm:grid-cols-3">
              <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
                Tokens <span className="font-mono text-foreground">{activeFrame.tokenUsage}</span>
              </div>
              <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
                Cost <span className="font-mono text-foreground">${activeFrame.cost.toFixed(2)}</span>
              </div>
              <div className="rounded-md border border-border bg-muted/40 px-3 py-2">
                Speed <span className="font-mono text-foreground">{speed}x</span>
              </div>
            </div>
            {[
              ["Prompt", activeFrame.prompt],
              ["Input", activeFrame.input],
              ["Output", activeFrame.output],
            ].map(([label, value]) => (
              <div key={label}>
                <h2 className="text-sm font-semibold text-foreground">{label}</h2>
                <p className="mt-2 rounded-md border border-border bg-background p-3 text-sm leading-6 text-muted-foreground">
                  {value}
                </p>
              </div>
            ))}
            <div>
              <h2 className="text-sm font-semibold text-foreground">Citations</h2>
              <div className="mt-2 flex flex-wrap gap-2">
                {activeFrame.citations.map((citation) => (
                  <Badge key={citation} variant="primary">
                    {citation}
                  </Badge>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
