import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badge = cva(
  "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium leading-none",
  {
    variants: {
      variant: {
        neutral: "bg-surface-2 text-muted",
        outline: "border border-line text-muted",
        accent: "bg-accent/15 text-accent",
        good: "bg-good/15 text-good",
        live: "bg-live/15 text-live",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ variant }), className)} {...props} />;
}

export function LiveBadge({ label = "Live" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md bg-live/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-live">
      <span className="live-dot h-1.5 w-1.5 rounded-full bg-live" />
      {label}
    </span>
  );
}
