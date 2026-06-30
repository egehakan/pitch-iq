"use client";
import {
  BookOpen,
  Check,
  FileText,
  ListOrdered,
  Loader2,
  Lock,
  type LucideIcon,
  MessageCircle,
  Radar,
  Search,
  Swords,
  Target,
  TrendingUp,
  Users,
  Wrench,
} from "lucide-react";
import type { AgentInfo, ToolStep } from "@/lib/companionChat";

const TOOL_ICON: Record<string, LucideIcon> = {
  get_fixture: Search,
  get_live_match_state: Radar,
  get_lineups: Users,
  get_standings: ListOrdered,
  get_head_to_head: Swords,
  get_team_form: TrendingUp,
  get_bracket_status: Lock,
  explain_rule: BookOpen,
};

const AGENT_ICON: Record<string, LucideIcon> = {
  qa_agent: Radar,
  prediction: Target,
  briefing: FileText,
  bracket_ops: Lock,
  chitchat: MessageCircle,
};

export function RunTrace({
  agent,
  tools,
  thinking,
}: {
  agent?: AgentInfo;
  tools: ToolStep[];
  thinking: boolean;
}) {
  if (!agent && tools.length === 0 && !thinking) return null;
  const AgentIcon = (agent && AGENT_ICON[agent.agent]) || Radar;

  return (
    <div className="mb-2.5 rounded-md border border-line bg-surface/60 px-3 py-2">
      <div className="flex items-center gap-2">
        <AgentIcon className="h-3.5 w-3.5 text-accent" />
        <span className="text-[12px] font-medium text-text">{agent?.label ?? "Routing"}</span>
        {!agent && thinking && <Loader2 className="h-3 w-3 animate-spin text-faint" />}
        {agent && (
          <span className="eyebrow ml-auto !text-[10px] text-faint">
            {tools.length > 0 ? `${tools.length} tool${tools.length > 1 ? "s" : ""}` : "reasoning"}
          </span>
        )}
      </div>

      {tools.length > 0 && (
        <ul className="mt-2 space-y-1.5 border-l border-line pl-3">
          {tools.map((t) => {
            const Icon = TOOL_ICON[t.name] ?? Wrench;
            return (
              <li key={t.id} className="flex items-center gap-2 text-[12px]">
                <Icon className="h-3 w-3 shrink-0 text-faint" />
                <span className="text-muted">{t.label}</span>
                {t.arg && <span className="truncate font-mono text-[11px] text-faint">· {t.arg}</span>}
                <span className="ml-auto shrink-0">
                  {t.status === "running" ? (
                    <Loader2 className="h-3 w-3 animate-spin text-accent" />
                  ) : (
                    <Check className="h-3 w-3 text-good" />
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
