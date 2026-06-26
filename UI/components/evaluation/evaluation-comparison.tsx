import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import type { EvaluationComparisonRow, HallucinationResult } from "@/types/domain";

type EvaluationComparisonProps = {
  comparison: EvaluationComparisonRow[];
  hallucination: HallucinationResult[];
};

export function EvaluationComparison({ comparison, hallucination }: EvaluationComparisonProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Single-prompt vs crew</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-[0.12em] text-muted-foreground">
                  <th scope="col" className="px-4 py-2 font-medium">
                    Metric
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Single-prompt
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Crew
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    &Delta;
                  </th>
                </tr>
              </thead>
              <tbody>
                {comparison.map((row) => (
                  <tr key={row.metric} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 text-foreground">{row.metric}</td>
                    <td className="px-4 py-3 font-mono text-muted-foreground">{row.singlePrompt}</td>
                    <td className="px-4 py-3 font-mono text-foreground">{row.crew}</td>
                    <td
                      className={cn(
                        "px-4 py-3 font-mono",
                        row.better ? "text-success-foreground" : "text-muted-foreground",
                      )}
                    >
                      {row.delta}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Verifier &mdash; seeded hallucination test</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-muted-foreground">
            25 ungrounded claims injected into adjudications.
          </p>
          {hallucination.map((result) => (
            <div key={result.label} className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{result.label}</span>
                <span className="font-mono text-foreground">
                  {result.count}/{result.total}
                </span>
              </div>
              <Progress value={result.count / result.total} tone={result.tone} />
            </div>
          ))}
          <p className="border-t border-border pt-3 text-xs text-muted-foreground">
            The single-prompt baseline catches 0 (it cannot reliably check itself).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
