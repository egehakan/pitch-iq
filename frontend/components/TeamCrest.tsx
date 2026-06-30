"use client";
import type { TeamOut } from "@/lib/types";

// Real crest image when available; a typographic monogram otherwise. No emoji.
export function TeamCrest({ team, size = 18 }: { team?: TeamOut | null; size?: number }) {
  if (team?.crest_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={team.crest_url}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        className="inline-block shrink-0 object-contain"
        style={{ width: size, height: size }}
      />
    );
  }
  const code =
    team?.short_name?.slice(0, 3).toUpperCase() ||
    team?.country_code?.toUpperCase() ||
    team?.name?.slice(0, 2).toUpperCase() ||
    "—";
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-[3px] bg-surface-2 font-mono font-medium text-faint"
      style={{ width: size, height: size, fontSize: Math.max(7, size * 0.42) }}
    >
      {code}
    </span>
  );
}
