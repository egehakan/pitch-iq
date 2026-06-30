import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.ComponentPropsWithRef<"input">) {
  return (
    <input
      data-slot="input"
      className={cn(
        "h-10 w-full rounded-md border border-line bg-surface-2 px-3 text-sm text-text placeholder:text-faint outline-none transition-colors focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/25 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: React.ComponentPropsWithRef<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "w-full resize-none rounded-md border border-line bg-surface-2 px-3 py-2.5 text-sm text-text placeholder:text-faint outline-none transition-colors focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/25 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[13px] font-medium text-muted">{label}</span>
      {children}
      {error ? (
        <span className="block text-xs text-live">{error}</span>
      ) : hint ? (
        <span className="block text-xs text-faint">{hint}</span>
      ) : null}
    </label>
  );
}
