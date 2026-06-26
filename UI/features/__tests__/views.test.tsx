import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { AuditLogsView } from "@/features/audit/audit-logs-view";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { EvaluationView } from "@/features/evaluation/evaluation-view";
import { IntakeView } from "@/features/intake/intake-view";

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("feature views render with data", () => {
  it("renders the Case Intake page", async () => {
    render(<IntakeView />, { wrapper: createWrapper() });

    expect(await screen.findByText("sample_gl_1000.csv")).toBeInTheDocument();
    expect(await screen.findByText("Rule pre-filter")).toBeInTheDocument();
  });

  it("renders the A/B Evaluation page", async () => {
    render(<EvaluationView />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Multi-agent crew vs single-prompt/i)).toBeInTheDocument();
    expect(await screen.findByText("Single-prompt vs crew")).toBeInTheDocument();
  });

  it("renders the Audit Log page", async () => {
    render(<AuditLogsView caseId="CASE-0007" />, { wrapper: createWrapper() });

    expect(await screen.findByText("Replay timeline")).toBeInTheDocument();
  });

  it("renders the Dashboard page", async () => {
    render(<DashboardView />, { wrapper: createWrapper() });

    expect((await screen.findAllByText(/ACME Holdings/i)).length).toBeGreaterThan(0);
  });
});
