import type { LucideIcon } from "lucide-react";
import { FileSearch } from "lucide-react";
import { Button } from "@/components/ui/button";

type EmptyStateProps = {
  title: string;
  description: string;
  actionLabel?: string;
  icon?: LucideIcon;
};

export function EmptyState({ title, description, actionLabel, icon: Icon = FileSearch }: EmptyStateProps) {
  return (
    <section className="rounded-lg border border-dashed border-border bg-card p-8 text-center">
      <Icon className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
      <h2 className="mt-4 text-base font-semibold text-foreground">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{description}</p>
      {actionLabel ? (
        <Button className="mt-5" variant="secondary">
          {actionLabel}
        </Button>
      ) : null}
    </section>
  );
}
