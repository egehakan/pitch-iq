"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Lock } from "lucide-react";
import type { BracketOut, FixtureOut, InterruptOut, Stage } from "@/lib/types";
import { useBracket, useConfirmSubmit, useSavePicks, useSubmitBracket } from "@/lib/queries";
import { MatchNode } from "./MatchNode";
import { SubmitConfirmDialog } from "./SubmitConfirmDialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/misc";

export function BracketBoard({
  bracketId,
  fixtures,
  stages,
}: {
  bracketId: string;
  fixtures: FixtureOut[];
  stages?: Stage[];
}) {
  const { data: bracket, isLoading } = useBracket(bracketId);
  const savePicks = useSavePicks(bracketId);
  const submit = useSubmitBracket(bracketId);
  const confirm = useConfirmSubmit(bracketId);
  const [dialog, setDialog] = useState<string | null>(null);

  if (isLoading || !bracket) return <Skeleton className="h-72 w-full" />;

  const editable = bracket.status === "draft";
  const rounds = (stages?.length ? stages : inferStages(fixtures)).sort((a, b) => a.order - b.order);
  const pickFor = (id: string) => bracket.picks.find((p) => p.fixture_id === id);

  const onPick = (fixture: FixtureOut, teamId: string) =>
    savePicks.mutate(
      [{ fixture_id: fixture.id, round_key: fixture.round_key ?? "R32", pick_type: "winner", predicted_winner_team_id: teamId }],
      { onError: (e) => toast.error(String(e)) },
    );

  const onSubmit = () =>
    submit.mutate(undefined, {
      onSuccess: (res: InterruptOut | BracketOut) =>
        "interrupt" in res ? setDialog(res.interrupt.summary) : toast.success("Bracket submitted"),
      onError: (e) => toast.error(String(e)),
    });

  const onApprove = () =>
    confirm.mutate(true, {
      onSuccess: (b) => {
        setDialog(null);
        toast.success(`Bracket ${b.status}`);
      },
      onError: (e) => toast.error(String(e)),
    });

  const onCancel = () => {
    if (!confirm.isPending) {
      confirm.mutate(false);
      setDialog(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <div className="flex items-center gap-3">
          <h2 className="font-display text-base font-bold tracking-tight text-text">{bracket.name}</h2>
          <Badge variant={bracket.status === "locked" || bracket.status === "scored" ? "good" : "neutral"}>
            {bracket.status}
          </Badge>
          <span className="text-[13px] text-faint">
            {bracket.picks.length} picks · <span className="tnum font-mono text-muted">{bracket.total_score}</span> pts
          </span>
        </div>
        {editable && (
          <Button size="sm" onClick={onSubmit} loading={submit.isPending}>
            <Lock className="h-3.5 w-3.5" />
            Submit and lock
          </Button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-5">
        <div className="flex min-w-max gap-7">
          {rounds.map((stage) => {
            const roundFixtures = fixtures.filter((f) => f.round_key === stage.key);
            return (
              <div key={stage.key} className="flex flex-col justify-around gap-4">
                <div className="eyebrow sticky top-0 pb-1">{stage.name}</div>
                {roundFixtures.map((fx) => (
                  <MatchNode
                    key={fx.id}
                    fixture={fx}
                    pick={pickFor(fx.id)}
                    editable={editable}
                    onPick={(teamId) => onPick(fx, teamId)}
                  />
                ))}
              </div>
            );
          })}
        </div>
        {editable && (
          <p className="mt-5 text-[13px] text-faint">
            Pick a winner in each match, then submit to lock. Locking needs one confirmation.
          </p>
        )}
      </div>

      <SubmitConfirmDialog
        open={!!dialog}
        summary={dialog ?? ""}
        pending={confirm.isPending}
        onApprove={onApprove}
        onCancel={onCancel}
      />
    </div>
  );
}

function inferStages(fixtures: FixtureOut[]): Stage[] {
  const seen = new Map<string, number>();
  let order = 0;
  for (const f of fixtures) {
    const k = f.round_key ?? "R";
    if (!seen.has(k)) seen.set(k, order++);
  }
  return [...seen.entries()].map(([key, ord]) => ({ key, name: key, order: ord }));
}
