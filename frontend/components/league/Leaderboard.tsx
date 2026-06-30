"use client";
import { useLeaderboard } from "@/lib/queries";
import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

export function Leaderboard({ leagueId }: { leagueId: string }) {
  const { data, isLoading } = useLeaderboard(leagueId);
  if (isLoading) return <Skeleton className="h-44 w-full" />;
  const rows = data?.rows ?? [];

  return (
    <Panel className="overflow-hidden">
      <div className="grid grid-cols-[3rem_1fr_5rem] items-center border-b border-line px-4 py-2.5">
        <span className="eyebrow">#</span>
        <span className="eyebrow">Player</span>
        <span className="eyebrow text-right">Points</span>
      </div>
      <ul className="divide-y divide-line">
        {rows.map((r) => (
          <li
            key={r.user_id}
            className="grid grid-cols-[3rem_1fr_5rem] items-center px-4 py-3 text-sm"
          >
            <span
              className={cn(
                "tnum font-mono",
                r.rank === 1 ? "font-bold text-accent" : "text-faint",
              )}
            >
              {String(r.rank).padStart(2, "0")}
            </span>
            <span className="truncate text-text">{r.display_name}</span>
            <span className="tnum text-right font-mono font-medium text-text">{r.total_score}</span>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="px-4 py-6 text-center text-[13px] text-faint">
            No members yet. Share the invite code to get a table going.
          </li>
        )}
      </ul>
    </Panel>
  );
}
