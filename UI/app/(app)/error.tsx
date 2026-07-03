"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

// Scoped to the (app) route group so a render error in any feature view is
// caught here - inside the AppShell, keeping the sidebar/nav usable - instead
// of bubbling past the shell to the root error boundary.
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <section className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-card">
        <p className="text-xs font-medium uppercase text-danger-foreground">Screen error</p>
        <h1 className="mt-2 text-xl font-semibold text-foreground">This screen could not render</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Retry the screen. If it repeats, inspect the service response or component boundary.
        </p>
        <Button className="mt-5" onClick={reset}>
          Try again
        </Button>
      </section>
    </div>
  );
}
