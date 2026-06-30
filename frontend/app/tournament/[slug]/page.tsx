"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { RightRail } from "@/components/companion/RightRail";
import { Tabs } from "@/components/ui/misc";
import { LiveBadge } from "@/components/ui/badge";
import { useEnsureBracket, useFixtures, useTournament } from "@/lib/queries";
import { isLive } from "@/lib/format";
import { cn } from "@/lib/utils";

function Companion({ slug }: { slug: string }) {
  const { data: tournament } = useTournament(slug);
  const { data: fixtures } = useFixtures(slug, true);
  const { data: bracket } = useEnsureBracket(tournament?.id);
  const [tab, setTab] = useState<"chat" | "match">("chat");

  if (!tournament || !fixtures || !bracket) {
    return <div className="flex h-full items-center justify-center text-sm text-faint">Loading companion</div>;
  }

  const stages = tournament.format_config?.stages ?? [];
  const order = (rk?: string | null) => stages.find((s) => s.key === rk)?.order ?? 99;
  const current = [...fixtures]
    .filter((f) => f.status === "NS" || isLive(f.status))
    .sort((a, b) => order(a.round_key) - order(b.round_key))[0];
  const currentStage = stages.find((s) => s.key === current?.round_key);
  const anyLive = fixtures.some((f) => isLive(f.status));

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-line px-5">
        <div className="flex items-baseline gap-2.5">
          <h1 className="font-display text-[15px] font-bold tracking-tight text-text">{tournament.name}</h1>
          {currentStage && <span className="eyebrow">{currentStage.name}</span>}
        </div>
        <div className="flex items-center gap-3">
          {anyLive && <LiveBadge />}
          <Tabs
            className="lg:hidden"
            active={tab}
            onChange={(k) => setTab(k as "chat" | "match")}
            tabs={[
              { key: "chat", label: "Ask" },
              { key: "match", label: "Match" },
            ]}
          />
        </div>
      </div>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className={cn("min-h-0 lg:border-r lg:border-line", tab !== "chat" && "hidden lg:block")}>
          <ChatPanel tournamentId={tournament.id} />
        </div>
        <aside className={cn("min-h-0 overflow-y-auto p-4", tab !== "match" && "hidden lg:block")}>
          <RightRail fixtures={fixtures} bracketId={bracket.id} />
        </aside>
      </div>
    </div>
  );
}

export default function TournamentPage() {
  const params = useParams<{ slug: string }>();
  return (
    <AppShell>
      <Companion slug={params.slug} />
    </AppShell>
  );
}
