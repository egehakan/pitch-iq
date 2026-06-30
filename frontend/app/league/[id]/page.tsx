"use client";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { Leaderboard } from "@/components/league/Leaderboard";

function LeagueView({ id }: { id: string }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-2xl px-6 py-10">
        <Link
          href="/"
          className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-text"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Dashboard
        </Link>
        <h1 className="font-display text-2xl font-bold tracking-tight text-text">League table</h1>
        <p className="mb-5 mt-1 text-sm text-muted">Ranked by total bracket points, updated as results land.</p>
        <Leaderboard leagueId={id} />
      </div>
    </div>
  );
}

export default function LeaguePage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <LeagueView id={params.id} />
    </AppShell>
  );
}
