"use client";
import { BookOpen, type LucideIcon, Search, Target, Trophy } from "lucide-react";
import { useCompanionChat } from "@/lib/companionChat";
import { MessageList } from "./MessageList";
import { Composer } from "./Composer";

const SUGGESTIONS: { icon: LucideIcon; text: string }[] = [
  { icon: Search, text: "What happened in Brazil vs Japan?" },
  { icon: Target, text: "Predict France vs Sweden" },
  { icon: BookOpen, text: "Why do referees add six minutes?" },
  { icon: Trophy, text: "How is my bracket doing?" },
];

export function ChatPanel({ tournamentId }: { tournamentId: string }) {
  const { messages, status, send, stop } = useCompanionChat(tournamentId);

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full w-full max-w-[44rem] flex-col justify-center px-5 py-10">
            <h2 className="font-display text-2xl font-bold tracking-tight text-text">
              What do you want to know?
            </h2>
            <p className="mt-1.5 max-w-md text-sm text-muted">
              Ask about any match and I will check the live data, the standings, or your bracket
              before answering. You will see exactly what I looked at.
            </p>
            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              {SUGGESTIONS.map(({ icon: Icon, text }) => (
                <button
                  key={text}
                  onClick={() => send(text)}
                  className="flex items-center gap-2.5 rounded-lg border border-line bg-surface px-3.5 py-2.5 text-left text-[13px] text-muted transition-colors hover:border-line-strong hover:text-text"
                >
                  <Icon className="h-4 w-4 shrink-0 text-faint" />
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <MessageList messages={messages} />
        )}
      </div>
      <Composer onSend={send} onStop={stop} running={status === "running"} />
    </div>
  );
}
