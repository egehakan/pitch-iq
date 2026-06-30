import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-medium transition-[background-color,color,border-color,opacity] duration-150 outline-none focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-ink disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        accent: "bg-accent text-on-accent hover:bg-accent-press",
        ghost: "text-muted hover:text-text hover:bg-surface-2",
        outline: "border border-line text-text hover:border-line-strong hover:bg-surface",
        danger: "border border-live/40 text-live hover:bg-live/10",
        subtle: "bg-surface-2 text-text hover:bg-line",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-9 px-4 text-sm",
        lg: "h-11 px-6 text-[15px]",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "accent", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export function Button({ className, variant, size, loading, children, disabled, ...props }: ButtonProps) {
  return (
    <button
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}
