"use client";

import { Settings } from "lucide-react";
import { SettingsForm } from "@/components/forms/settings-form";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { useSettings } from "@/hooks/use-settings";

export function SettingsView() {
  const { data, error, isLoading, refetch } = useSettings();

  if (isLoading) {
    return <LoadingState label="Loading settings" />;
  }

  if (error || !data) {
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Settings"
        title="Governance controls"
        description="Configure model routing, confidence thresholds, materiality policy, reviewer separation, and audit log enforcement."
        actions={
          <Button variant="secondary">
            <Settings className="h-4 w-4" aria-hidden="true" />
            Policy history
          </Button>
        }
      />

      <SettingsForm settings={data} />
    </div>
  );
}
