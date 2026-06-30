"use client";
import Link from "next/link";
import { ChevronRight, Radio } from "lucide-react";
import type { FixtureOut } from "@/lib/types";
import { useBracket } from "@/lib/queries";
import { teamLabel } from "@/lib/format";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Badge } from "@/components/ui/badge";
import { TeamCrest } from "@/components/TeamCrest";
import { LiveMatchCard } from "@/components/live/LiveMatchCard";

function statusVariant(s: string) {
  if (s === "locked" || s === "scored") return "good" as const;
  return "neutral" as const;
}

export function RightRail({ fixtures, bracketId }: { fixtures: FixtureOut[]; bracketId: string }) {
  const { data: bracket } = useBracket(bracketId);
  const nextUp = fixtures
    .filter((f) => f.status === "NS" && f.kickoff_at && (f.home || f.home_placeholder))
    .sort((a, b) => +new Date(a.kickoff_at!) - +new Date(b.kickoff_at!))
    .slice(0, 5);

  return (
    <div className="flex flex-col gap-4">
      <Panel className="overflow-hidden">
        <PanelHeader label="Match" icon={<Radio className="h-3.5 w-3.5" />} />
        <LiveMatchCard fixtures={fixtures} />
      </Panel>

      <Panel className="overflow-hidden">
        <PanelHeader
          label="Your bracket"
          actions={
            <Link
              href={`/bracket/${bracketId}`}
              className="flex items-center gap-0.5 text-[12px] text-accent hover:underline"
            >
              Edit
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
        <div className="flex items-center justify-between px-4 py-3.5">
          <div>
            <div className="text-sm font-medium text-text">{bracket?.name ?? "My bracket"}</div>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={statusVariant(bracket?.status ?? "draft")}>{bracket?.status ?? "draft"}</Badge>
              <span className="text-[12px] text-faint">
                {bracket?.picks.length ?? 0} picks
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="tnum font-display text-2xl font-bold text-text">{bracket?.total_score ?? 0}</div>
            <div className="eyebrow !text-[10px]">points</div>
          </div>
        </div>
      </Panel>

      <Panel className="overflow-hidden">
        <PanelHeader label="Next up" />
        <ul className="divide-y divide-line">
          {nextUp.map((fx) => (
            <li key={fx.id} className="flex items-center gap-3 px-4 py-2.5">
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                {[{ t: fx.home, p: fx.home_placeholder }, { t: fx.away, p: fx.away_placeholder }].map((r, i) => (
                  <span key={i} className="flex items-center gap-2 truncate text-[13px] text-muted">
                    <TeamCrest team={r.t} size={15} />
                    {teamLabel(r.t, r.p)}
                  </span>
                ))}
              </div>
              <span className="tnum shrink-0 text-right font-mono text-[11px] text-faint">
                {fx.kickoff_at
                  ? new Date(fx.kickoff_at).toLocaleString(undefined, {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "TBD"}
              </span>
            </li>
          ))}
          {nextUp.length === 0 && (
            <li className="px-4 py-4 text-[13px] text-faint">No upcoming matches.</li>
          )}
        </ul>
      </Panel>
    </div>
  );
}
