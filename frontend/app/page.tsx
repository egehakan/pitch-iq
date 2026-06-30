"use client";
import Link from "next/link";
import { ArrowRight, MessageSquare, Target, Trophy } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useEnsureBracket, useFixtures, useTournament } from "@/lib/queries";
import { BriefingList } from "@/components/briefing/BriefingList";
import { InvitePanel } from "@/components/league/InvitePanel";
import { LiveMatchCard } from "@/components/live/LiveMatchCard";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { buttonVariants } from "@/components/ui/button";
import { Badge, LiveBadge } from "@/components/ui/badge";
import { TeamCrest } from "@/components/TeamCrest";
import { fixtureTitle, isLive } from "@/lib/format";
import type { FixtureOut } from "@/lib/types";

const SLUG = "world-cup-2026";

const CAPABILITIES = [
  { icon: MessageSquare, title: "Grounded answers", body: "Every reply checks the live match, standings, or your bracket first, and shows what it looked at." },
  { icon: Target, title: "Tested predictions", body: "A generator and a critic argue it out against the no-vig market line before you see a call." },
  { icon: Trophy, title: "A bracket that scores", body: "Pick the knockouts, lock with one confirmation, and climb a private league table." },
];

function Dashboard() {
  const { data: tournament } = useTournament(SLUG);
  const { data: fixtures } = useFixtures(SLUG, true);
  const { data: bracket } = useEnsureBracket(tournament?.id);

  const fx = fixtures ?? [];
  const anyLive = fx.some((f) => isLive(f.status));
  const upcoming = fx
    .filter((f) => f.status === "NS" && f.kickoff_at && (f.home || f.home_placeholder))
    .sort((a, b) => +new Date(a.kickoff_at!) - +new Date(b.kickoff_at!));

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-6xl px-6 py-8 lg:py-12">
        {/* Hero */}
        <section className="grid items-center gap-8 lg:grid-cols-[1fr_22rem]">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="eyebrow">{tournament?.name ?? "FIFA World Cup 2026"}</span>
              {anyLive && <LiveBadge />}
            </div>
            <h1 className="mt-3 font-display text-4xl font-extrabold leading-[1.05] tracking-tight text-text sm:text-5xl">
              Ask the match
              <br />
              <span className="text-accent">anything.</span>
            </h1>
            <p className="mt-4 max-w-md text-[15px] leading-relaxed text-muted">
              A companion for the knockout rounds. Live answers grounded in real data, predictions
              tested against the market, and a bracket you can lock. The working is always shown.
            </p>
            <div className="mt-6 flex flex-wrap gap-2.5">
              <Link href={`/tournament/${SLUG}`} className={buttonVariants({ size: "lg" })}>
                Open the companion
                <ArrowRight className="h-4 w-4" />
              </Link>
              {bracket && (
                <Link
                  href={`/bracket/${bracket.id}`}
                  className={buttonVariants({ size: "lg", variant: "outline" })}
                >
                  Edit my bracket
                </Link>
              )}
            </div>
          </div>
          <Panel className="overflow-hidden">
            <PanelHeader label={anyLive ? "Live now" : "Next match"} />
            <LiveMatchCard fixtures={fx} />
          </Panel>
        </section>

        {/* Capabilities */}
        <section className="mt-14 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3">
          {CAPABILITIES.map(({ icon: Icon, title, body }) => (
            <div key={title} className="bg-surface p-5">
              <Icon className="h-5 w-5 text-accent" />
              <h3 className="mt-3 font-display text-[15px] font-bold tracking-tight text-text">{title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{body}</p>
            </div>
          ))}
        </section>

        {/* Upcoming + briefings */}
        <section className="mt-10 grid gap-6 lg:grid-cols-2">
          <Panel className="overflow-hidden">
            <PanelHeader label="Upcoming" />
            <ul className="divide-y divide-line">
              {upcoming.slice(0, 6).map((fxr: FixtureOut) => (
                <li key={fxr.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                  <span className="flex min-w-0 items-center gap-2 truncate text-[13px] text-muted">
                    <TeamCrest team={fxr.home} size={16} />
                    <TeamCrest team={fxr.away} size={16} />
                    <span className="truncate">{fixtureTitle(fxr)}</span>
                  </span>
                  <span className="tnum shrink-0 font-mono text-[11px] text-faint">
                    {fxr.kickoff_at
                      ? new Date(fxr.kickoff_at).toLocaleString(undefined, {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "TBD"}
                  </span>
                </li>
              ))}
              {upcoming.length === 0 && <li className="px-4 py-5 text-[13px] text-faint">No upcoming matches.</li>}
            </ul>
          </Panel>

          <div>
            <div className="mb-3 flex items-center gap-2">
              <span className="eyebrow">Briefings</span>
              <Badge variant="neutral">written before kickoff</Badge>
            </div>
            <BriefingList fixtures={upcoming.slice(0, 5)} />
          </div>
        </section>

        {/* Leagues */}
        {tournament && bracket && (
          <section className="mt-10">
            <div className="mb-3 eyebrow">Private leagues</div>
            <InvitePanel tournamentId={tournament.id} bracketId={bracket.id} />
          </section>
        )}
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}
