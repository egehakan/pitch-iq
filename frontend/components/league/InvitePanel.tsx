"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Copy, Plus, UserPlus } from "lucide-react";
import { useCreateLeague, useJoinLeague } from "@/lib/queries";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";

export function InvitePanel({ tournamentId, bracketId }: { tournamentId: string; bracketId?: string }) {
  const create = useCreateLeague();
  const join = useJoinLeague();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [invite, setInvite] = useState<string | null>(null);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel className="overflow-hidden">
        <PanelHeader label="Create a league" icon={<Plus className="h-3.5 w-3.5" />} />
        <div className="space-y-3 p-4">
          <Field label="League name">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="The office cup" />
          </Field>
          <Button
            disabled={!name}
            loading={create.isPending}
            onClick={() =>
              create.mutate(
                { tournament_id: tournamentId, name },
                {
                  onSuccess: (l) => {
                    setInvite(l.invite_code);
                    toast.success(`Created ${l.name}`);
                  },
                  onError: (e) => toast.error(String(e)),
                },
              )
            }
          >
            Create league
          </Button>
          {invite && (
            <button
              onClick={() => {
                navigator.clipboard?.writeText(invite);
                toast.success("Invite code copied");
              }}
              className="flex items-center gap-2 rounded-md border border-line bg-surface-2 px-3 py-2 text-[13px]"
            >
              <span className="text-faint">Invite code</span>
              <span className="tnum font-mono font-medium text-text">{invite}</span>
              <Copy className="h-3.5 w-3.5 text-faint" />
            </button>
          )}
        </div>
      </Panel>

      <Panel className="overflow-hidden">
        <PanelHeader label="Join a league" icon={<UserPlus className="h-3.5 w-3.5" />} />
        <div className="space-y-3 p-4">
          <Field label="Invite code">
            <Input
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              placeholder="ABCD1234"
              className="font-mono"
            />
          </Field>
          <Button
            variant="outline"
            disabled={!code || !bracketId}
            loading={join.isPending}
            onClick={() =>
              join.mutate(
                { invite_code: code, bracket_id: bracketId! },
                {
                  onSuccess: (l) => toast.success(`Joined ${l.name}`),
                  onError: (e) => toast.error(String(e)),
                },
              )
            }
          >
            {bracketId ? "Join league" : "Create a bracket first"}
          </Button>
        </div>
      </Panel>
    </div>
  );
}
