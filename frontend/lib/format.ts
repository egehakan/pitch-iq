import type { FixtureOut, TeamOut } from "@/lib/types";

// NB: football-data uses "PEN" to mean *finished via shootout* (not penalties in progress).
export const LIVE_STATUSES = new Set(["1H", "HT", "2H", "ET", "BT", "P", "LIVE"]);
export const FINISHED_STATUSES = new Set(["FT", "AET", "PEN"]);

export function isLive(status: string): boolean {
  return LIVE_STATUSES.has(status);
}

export function teamLabel(t: TeamOut | null | undefined, placeholder?: string | null): string {
  return t?.name ?? placeholder ?? "TBD";
}

export function fixtureTitle(fx: FixtureOut): string {
  return `${teamLabel(fx.home, fx.home_placeholder)} vs ${teamLabel(fx.away, fx.away_placeholder)}`;
}

export function statusLabel(fx: FixtureOut): string {
  if (isLive(fx.status)) return "LIVE";
  if (FINISHED_STATUSES.has(fx.status)) return "FT";
  if (fx.kickoff_at) {
    return new Date(fx.kickoff_at).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return fx.status;
}

export function flag(countryCode?: string | null): string {
  if (!countryCode || countryCode.length !== 2) return "🏳️";
  const cp = [...countryCode.toUpperCase()].map((c) => 127397 + c.charCodeAt(0));
  return String.fromCodePoint(...cp);
}
