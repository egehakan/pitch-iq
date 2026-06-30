"use client";
import { Check } from "lucide-react";
import { teamLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import { TeamCrest } from "@/components/TeamCrest";
import type { FixtureOut, PickOut } from "@/lib/types";

export function MatchNode({
  fixture,
  pick,
  editable,
  onPick,
}: {
  fixture: FixtureOut;
  pick?: PickOut;
  editable: boolean;
  onPick?: (teamId: string) => void;
}) {
  const rows = [
    { team: fixture.home, placeholder: fixture.home_placeholder, score: fixture.score.home },
    { team: fixture.away, placeholder: fixture.away_placeholder, score: fixture.score.away },
  ];
  const pickedId = pick?.predicted_winner_team_id ?? pick?.predicted_team_id ?? null;
  const winnerId = fixture.score.home != null && fixture.score.away != null
    ? fixture.score.home > fixture.score.away
      ? fixture.home?.id
      : fixture.score.away > fixture.score.home
        ? fixture.away?.id
        : null
    : null;

  return (
    <div className="w-[13.5rem] overflow-hidden rounded-md border border-line bg-surface">
      {rows.map((r, i) => {
        const id = r.team?.id ?? null;
        const picked = !!id && pickedId === id;
        const isWinner = !!id && winnerId === id;
        const correct = picked && isWinner;
        const clickable = editable && !!id;
        return (
          <button
            key={i}
            disabled={!clickable}
            onClick={() => clickable && onPick?.(id!)}
            className={cn(
              "flex w-full items-center gap-2 px-2.5 py-2 text-left text-[13px] transition-colors",
              i === 0 && "border-b border-line",
              picked ? "bg-accent/10" : "",
              clickable && "hover:bg-surface-2",
            )}
          >
            <TeamCrest team={r.team} size={17} />
            <span
              className={cn(
                "flex-1 truncate",
                isWinner ? "font-semibold text-text" : "text-muted",
                !r.team && "text-faint",
              )}
            >
              {teamLabel(r.team, r.placeholder)}
            </span>
            {picked && (
              <Check className={cn("h-3 w-3 shrink-0", correct ? "text-good" : "text-accent")} />
            )}
            {r.score != null && (
              <span className="tnum w-4 text-right font-mono text-[13px] text-muted">{r.score}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
