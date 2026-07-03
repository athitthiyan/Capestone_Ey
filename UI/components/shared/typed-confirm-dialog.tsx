"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type TypedConfirmDialogProps = {
  trigger: React.ReactNode;
  title: string;
  description: string;
  /** The exact phrase the user must type to enable the confirm button. */
  confirmPhrase: string;
  confirmLabel?: string;
  onConfirm: () => void;
};

/**
 * Keyboard-accessible replacement for window.confirm() on irreversible,
 * cross-case actions (bulk delete). Requires typing an exact phrase before
 * the destructive button is enabled, matching the audit-tool expectation
 * that destructive actions leave no room for an accidental single click.
 */
export function TypedConfirmDialog({
  trigger,
  title,
  description,
  confirmPhrase,
  confirmLabel = "Delete",
  onConfirm,
}: TypedConfirmDialogProps) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const canConfirm = typed === confirmPhrase;

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setTyped("");
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-card p-6 shadow-panel">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-danger-soft text-danger-foreground">
              <AlertTriangle className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <Dialog.Title className="text-base font-semibold text-foreground">{title}</Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted-foreground">{description}</Dialog.Description>
            </div>
          </div>

          <div className="mt-4">
            <label htmlFor="typed-confirm-input" className="text-sm font-medium text-foreground">
              Type <span className="font-mono text-danger-foreground">{confirmPhrase}</span> to confirm
            </label>
            <Input
              id="typed-confirm-input"
              className="mt-2"
              autoComplete="off"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
            />
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button type="button" variant="secondary">
                Cancel
              </Button>
            </Dialog.Close>
            <Button
              type="button"
              variant="danger"
              disabled={!canConfirm}
              onClick={() => {
                onConfirm();
                handleOpenChange(false);
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
