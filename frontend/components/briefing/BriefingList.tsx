"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { FixtureOut } from "@/lib/types";
import { fixtureTitle, statusLabel } from "@/lib/format";
import { TeamCrest } from "@/components/TeamCrest";
import { Panel } from "@/components/ui/panel";
import { BriefingCard } from "./BriefingCard";

export function BriefingList({ fixtures }: { fixtures: FixtureOut[] }) {
  const items = fixtures.filter((f) => f.home || f.home_placeholder);
  const [open, setOpen] = useState<string | null>(items[0]?.id ?? null);

  if (items.length === 0) {
    return <p className="text-[13px] text-faint">No briefings yet. They appear before kickoff.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((fx) => {
        const expanded = open === fx.id;
        return (
          <Panel key={fx.id} className="overflow-hidden">
            <button
              onClick={() => setOpen(expanded ? null : fx.id)}
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-2"
            >
              <span className="flex min-w-0 items-center gap-2">
                <TeamCrest team={fx.home} size={16} />
                <TeamCrest team={fx.away} size={16} />
                <span className="truncate text-[13px] font-medium text-text">{fixtureTitle(fx)}</span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="tnum font-mono text-[11px] text-faint">{statusLabel(fx)}</span>
                {expanded ? (
                  <ChevronDown className="h-4 w-4 text-faint" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-faint" />
                )}
              </span>
            </button>
            {expanded && <BriefingCard fixtureId={fx.id} />}
          </Panel>
        );
      })}
    </div>
  );
}
