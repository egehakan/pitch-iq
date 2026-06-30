"use client";
import { useEffect, useRef } from "react";
import type { ChatMessage } from "@/lib/companionChat";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: ChatMessage[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="mx-auto flex w-full max-w-[44rem] flex-col gap-5 px-5 py-6">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      <div ref={end} className="h-px" />
    </div>
  );
}
