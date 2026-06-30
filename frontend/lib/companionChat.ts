"use client";
import { useCallback, useId, useRef, useState } from "react";

export type ToolStep = {
  id: string;
  name: string;
  label: string;
  arg?: string;
  status: "running" | "done";
};

export type AgentInfo = { route: string; agent: string; label: string };

export type ChatMessage =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      agent?: AgentInfo;
      tools: ToolStep[];
      text: string;
      status: "thinking" | "streaming" | "done" | "error";
    };

type Event =
  | { type: "route"; route: string; agent: string; label: string }
  | { type: "tool"; id: string; name: string; label?: string; arg?: string; status: "running" | "done" }
  | { type: "text"; delta: string }
  | { type: "error"; message: string }
  | { type: "done" };

let _seq = 0;
const uid = () => `m${Date.now().toString(36)}${(_seq++).toString(36)}`;

export function useCompanionChat(tournamentId: string) {
  const rawThread = useId();
  const threadId = useRef(`chat-${tournamentId}-${rawThread.replace(/:/g, "")}`);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "running">("idle");
  const abortRef = useRef<AbortController | null>(null);

  const patchAssistant = useCallback((id: string, fn: (m: Extract<ChatMessage, { role: "assistant" }>) => void) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== id || m.role !== "assistant") return m;
        const next = { ...m, tools: [...m.tools] };
        fn(next);
        return next;
      }),
    );
  }, []);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || status === "running") return;
      const userMsg: ChatMessage = { id: uid(), role: "user", text };
      const aId = uid();
      const assistant: ChatMessage = { id: aId, role: "assistant", tools: [], text: "", status: "thinking" };
      setMessages((prev) => [...prev, userMsg, assistant]);
      setStatus("running");

      const ctrl = new AbortController();
      abortRef.current = ctrl;
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ message: text, thread_id: threadId.current, tournament_id: tournamentId }),
          signal: ctrl.signal,
        });
        if (!res.body) throw new Error("no stream");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let nl: number;
          while ((nl = buf.indexOf("\n")) >= 0) {
            const raw2 = buf.slice(0, nl).trim();
            buf = buf.slice(nl + 1);
            if (!raw2) continue;
            let ev: Event;
            try {
              ev = JSON.parse(raw2);
            } catch {
              continue;
            }
            if (ev.type === "route") {
              patchAssistant(aId, (m) => {
                m.agent = { route: ev.route, agent: ev.agent, label: ev.label };
              });
            } else if (ev.type === "tool") {
              patchAssistant(aId, (m) => {
                const existing = m.tools.find((t) => t.id === ev.id);
                if (existing) existing.status = ev.status;
                else
                  m.tools.push({
                    id: ev.id,
                    name: ev.name,
                    label: ev.label || ev.name,
                    arg: ev.arg,
                    status: ev.status,
                  });
              });
            } else if (ev.type === "text") {
              patchAssistant(aId, (m) => {
                m.text += ev.delta;
                m.status = "streaming";
              });
            } else if (ev.type === "error") {
              patchAssistant(aId, (m) => {
                m.text = ev.message;
                m.status = "error";
              });
            }
          }
        }
        patchAssistant(aId, (m) => {
          if (m.status !== "error") m.status = "done";
        });
      } catch (e) {
        if ((e as Error).name !== "AbortError") {
          patchAssistant(aId, (m) => {
            m.status = "error";
            m.text = m.text || "Something went wrong reaching the companion.";
          });
        } else {
          patchAssistant(aId, (m) => {
            m.status = "done";
          });
        }
      } finally {
        setStatus("idle");
        abortRef.current = null;
      }
    },
    [status, tournamentId, patchAssistant],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, status, send, stop };
}
