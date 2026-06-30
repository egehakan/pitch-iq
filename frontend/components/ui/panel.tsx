import * as React from "react";
import { cn } from "@/lib/utils";

export function Panel({
  className,
  flush,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { flush?: boolean }) {
  return (
    <div
      data-slot="panel"
      className={cn(
        "rounded-lg border border-line bg-surface",
        flush ? "" : "",
        className,
      )}
      {...props}
    />
  );
}

export function PanelHeader({
  label,
  icon,
  actions,
  className,
}: {
  label: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-11 items-center justify-between gap-2 border-b border-line px-4",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {icon && <span className="text-muted">{icon}</span>}
        <span className="eyebrow">{label}</span>
      </div>
      {actions}
    </div>
  );
}
