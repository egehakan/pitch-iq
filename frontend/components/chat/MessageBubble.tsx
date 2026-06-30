"use client";
import ReactMarkdown from "react-markdown";
import { AlertCircle } from "lucide-react";
import type { ChatMessage } from "@/lib/companionChat";
import { RunTrace } from "./RunTrace";
import { cn } from "@/lib/utils";

export function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-xl rounded-br-sm bg-surface-2 px-3.5 py-2 text-[15px] text-text">
          {message.text}
        </div>
      </div>
    );
  }

  const streaming = message.status === "streaming";
  const thinking = message.status === "thinking";
  return (
    <div className="rise">
      <RunTrace agent={message.agent} tools={message.tools} thinking={thinking} />
      {message.status === "error" ? (
        <div className="flex items-center gap-2 text-[13px] text-live">
          <AlertCircle className="h-4 w-4" />
          {message.text}
        </div>
      ) : message.text ? (
        <div className={cn("prose-chat text-text", streaming && "caret")}>
          <ReactMarkdown>{message.text}</ReactMarkdown>
        </div>
      ) : (
        thinking && <div className="text-[13px] text-faint">Thinking…</div>
      )}
    </div>
  );
}
