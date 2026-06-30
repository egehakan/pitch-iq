"use client";
import ReactMarkdown from "react-markdown";
import { useBriefing } from "@/lib/queries";
import { Skeleton } from "@/components/ui/misc";

export function BriefingCard({ fixtureId }: { fixtureId: string }) {
  const { data, isLoading, isError } = useBriefing(fixtureId);
  const generating = isLoading || data?.status === "generating" || data?.status === "pending";

  if (generating) {
    return (
      <div className="space-y-2 border-t border-line px-4 py-3.5">
        <Skeleton className="h-3.5 w-2/3" />
        <Skeleton className="h-3.5 w-full" />
        <Skeleton className="h-3.5 w-5/6" />
        <p className="pt-1 text-[12px] text-faint">Writing the briefing</p>
      </div>
    );
  }
  if (isError || !data?.content) {
    return <p className="border-t border-line px-4 py-3.5 text-[13px] text-faint">No briefing available.</p>;
  }
  return (
    <div className="prose-chat max-h-80 overflow-y-auto border-t border-line px-4 py-3.5 text-text">
      <ReactMarkdown>{data.content}</ReactMarkdown>
    </div>
  );
}
