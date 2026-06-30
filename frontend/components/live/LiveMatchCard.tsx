"use client";
import { ArrowRightLeft, CircleDot, Clock, type LucideIcon, Square, Tv } from "lucide-react";
import { useLiveFeed } from "@/hooks/useLiveFeed";
import { isLive, teamLabel } from "@/lib/format";
import type { FixtureOut, LiveEvent } from "@/lib/types";
import { TeamCrest } from "@/components/TeamCrest";
import { LiveBadge } from "@/components/ui/badge";

function eventIcon(type: string): { Icon: LucideIcon; cls: string } {
  const t = type.toLowerCase();
  if (t.includes("goal")) return { Icon: CircleDot, cls: "text-accent" };
  if (t.includes("card")) return { Icon: Square, cls: t.includes("red") ? "text-live" : "text-accent" };
  if (t.includes("subst")) return { Icon: ArrowRightLeft, cls: "text-muted" };
  if (t.includes("var")) return { Icon: Tv, cls: "text-muted" };
  return { Icon: CircleDot, cls: "text-faint" };
}

function TeamRow({
  team,
  placeholder,
  score,
  lead,
}: {
  team: FixtureOut["home"];
  placeholder?: string | null;
  score: number | null;
  lead: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <TeamCrest team={team} size={22} />
      <span className={`flex-1 truncate text-sm ${lead ? "font-semibold text-text" : "text-muted"}`}>
        {teamLabel(team, placeholder)}
      </span>
      <span className="tnum font-display text-xl font-bold text-text">
        {score ?? <span className="text-faint">·</span>}
      </span>
    </div>
  );
}

export function LiveMatchCard({ fixtures }: { fixtures: FixtureOut[] }) {
  const liveNow = fixtures.find((f) => isLive(f.status));
  const upcoming = fixtures
    .filter((f) => f.status === "NS" && f.kickoff_at && (f.home || f.home_placeholder))
    .sort((a, b) => +new Date(a.kickoff_at!) - +new Date(b.kickoff_at!));
  const fx = liveNow ?? upcoming[0] ?? fixtures[0];
  const live = !!fx && isLive(fx.status);
  const { events, score } = useLiveFeed(fx?.id, live);

  if (!fx) {
    return <p className="px-4 py-6 text-sm text-faint">No matches to follow yet.</p>;
  }

  const home = score?.home ?? fx.score.home ?? null;
  const away = score?.away ?? fx.score.away ?? null;
  const kickoff = fx.kickoff_at
    ? new Date(fx.kickoff_at).toLocaleString(undefined, {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div>
      <div className="flex items-center justify-between px-4 pt-3.5">
        <span className="eyebrow">{fx.round_key === "GROUP" ? "Group stage" : fx.round_key}</span>
        {live ? <LiveBadge label={`${score?.minute ?? fx.status}'`} /> : <span className="text-[11px] text-faint">Upcoming</span>}
      </div>

      <div className="space-y-2 px-4 py-3">
        <TeamRow team={fx.home} placeholder={fx.home_placeholder} score={home} lead={(home ?? 0) > (away ?? 0)} />
        <TeamRow team={fx.away} placeholder={fx.away_placeholder} score={away} lead={(away ?? 0) > (home ?? 0)} />
      </div>

      <div className="flex items-center gap-1.5 border-t border-line px-4 py-2 text-[11px] text-faint">
        <Clock className="h-3 w-3" />
        {live ? `${score?.minute ?? ""}' in play` : kickoff}
        {fx.venue && <span className="truncate">· {fx.venue}</span>}
      </div>

      {live && events.length > 0 && (
        <ul className="max-h-44 space-y-1 overflow-y-auto border-t border-line px-4 py-2.5">
          {[...events].reverse().map((e: LiveEvent, i) => {
            const { Icon, cls } = eventIcon(e.type);
            return (
              <li key={i} className="flex items-center gap-2 text-[12px]">
                <span className="tnum w-7 shrink-0 font-mono text-faint">
                  {`${e.minute ?? "?"}${e.extra ? `+${e.extra}` : ""}'`}
                </span>
                <Icon className={`h-3 w-3 shrink-0 ${cls}`} />
                <span className="truncate text-muted">
                  {e.player || e.detail || e.type}
                  {e.team ? <span className="text-faint"> · {e.team}</span> : null}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
