"use client";
import { Lock } from "lucide-react";
import { Dialog } from "@/components/ui/misc";
import { Button } from "@/components/ui/button";

// The browser surface of the agent's interrupt() in bracket_ops (human-in-the-loop).
export function SubmitConfirmDialog({
  open,
  summary,
  pending,
  onApprove,
  onCancel,
}: {
  open: boolean;
  summary: string;
  pending: boolean;
  onApprove: () => void;
  onCancel: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <div className="space-y-4">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Lock className="h-4 w-4" />
          </span>
          <h3 className="font-display text-lg font-bold tracking-tight text-text">Lock your bracket</h3>
        </div>
        <p className="text-sm leading-relaxed text-muted">{summary}</p>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onCancel} disabled={pending}>
            Keep editing
          </Button>
          <Button onClick={onApprove} loading={pending}>
            Submit and lock
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
