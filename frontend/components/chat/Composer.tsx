"use client";
import { useRef } from "react";
import { ArrowUp, Square } from "lucide-react";
import { Textarea } from "@/components/ui/field";
import { cn } from "@/lib/utils";

export function Composer({
  onSend,
  onStop,
  running,
}: {
  onSend: (text: string) => void;
  onStop: () => void;
  running: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const v = ref.current?.value ?? "";
    if (!v.trim() || running) return;
    onSend(v);
    if (ref.current) {
      ref.current.value = "";
      ref.current.style.height = "auto";
    }
  };

  return (
    <div className="border-t border-line bg-ink/80 px-5 py-3 backdrop-blur">
      <div className="mx-auto flex w-full max-w-[44rem] items-end gap-2 rounded-xl border border-line bg-surface px-3 py-2 transition-colors focus-within:border-line-strong">
        <Textarea
          ref={ref}
          rows={1}
          placeholder="Ask about a match, a rule, a prediction, or your bracket"
          className="max-h-40 min-h-0 flex-1 border-0 bg-transparent px-0 py-1.5 focus-visible:ring-0"
          onInput={(e) => {
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button
          type="button"
          onClick={running ? onStop : submit}
          aria-label={running ? "Stop" : "Send"}
          className={cn(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors",
            running
              ? "bg-surface-2 text-text hover:bg-line"
              : "bg-accent text-on-accent hover:bg-accent-press",
          )}
        >
          {running ? <Square className="h-3.5 w-3.5" /> : <ArrowUp className="h-4 w-4" />}
        </button>
      </div>
      <p className="mx-auto mt-1.5 max-w-[44rem] text-center text-[11px] text-faint">
        Grounded in live data. Answers can be wrong; check the score that matters.
      </p>
    </div>
  );
}
