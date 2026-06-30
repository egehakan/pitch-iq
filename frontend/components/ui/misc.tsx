"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-surface-2", className)} {...props} />;
}

export function ScrollArea({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("overflow-y-auto overscroll-contain", className)} {...props} />;
}

export function Dialog({
  open,
  onOpenChange,
  children,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  children: React.ReactNode;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onOpenChange(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-ink/70"
        onClick={() => onOpenChange(false)}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        className="rise relative z-10 w-full max-w-md rounded-xl border border-line-strong bg-surface p-5 shadow-2xl shadow-ink/60"
      >
        {children}
      </div>
    </div>
  );
}

export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: { key: string; label: string }[];
  active: string;
  onChange: (k: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("inline-flex rounded-lg border border-line bg-surface p-0.5", className)}>
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            "rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors",
            active === t.key ? "bg-surface-2 text-text" : "text-muted hover:text-text",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
