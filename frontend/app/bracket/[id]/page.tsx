"use client";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { BracketBoard } from "@/components/bracket/BracketBoard";
import { useFixtures, useTournament } from "@/lib/queries";

const SLUG = "world-cup-2026";

function Editor({ bracketId }: { bracketId: string }) {
  const { data: tournament } = useTournament(SLUG);
  const { data: fixtures } = useFixtures(SLUG);

  if (!tournament || !fixtures) {
    return <div className="flex h-full items-center justify-center text-sm text-faint">Loading bracket</div>;
  }

  return <BracketBoard bracketId={bracketId} fixtures={fixtures} stages={tournament.format_config?.stages} />;
}

export default function BracketPage() {
  const params = useParams<{ id: string }>();
  return (
    <AppShell>
      <Editor bracketId={params.id} />
    </AppShell>
  );
}
