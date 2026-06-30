"use client";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  BracketOut,
  BriefingOut,
  FixtureOut,
  InterruptOut,
  LeaderboardOut,
  LeagueOut,
  StandingsOut,
  TournamentOut,
  UserOut,
} from "@/lib/types";

export const keys = {
  me: ["me"] as const,
  tournament: (slug: string) => ["tournament", slug] as const,
  fixtures: (slug: string) => ["fixtures", slug] as const,
  standings: (slug: string) => ["standings", slug] as const,
  brackets: (tid: string) => ["brackets", tid] as const,
  bracket: (id: string) => ["bracket", id] as const,
  briefing: (fid: string) => ["briefing", fid] as const,
  leaderboard: (id: string) => ["leaderboard", id] as const,
};

export const useMe = () =>
  useQuery({ queryKey: keys.me, queryFn: () => api.get<UserOut>("/api/me"), retry: false });

export const useTournament = (slug: string) =>
  useQuery({ queryKey: keys.tournament(slug), queryFn: () => api.get<TournamentOut>(`/api/tournaments/${slug}`) });

export const useFixtures = (slug: string, live = false) =>
  useQuery({
    queryKey: keys.fixtures(slug),
    queryFn: () => api.get<FixtureOut[]>(`/api/tournaments/${slug}/fixtures`),
    refetchInterval: live ? 20_000 : false,
  });

export const useStandings = (slug: string) =>
  useQuery({ queryKey: keys.standings(slug), queryFn: () => api.get<StandingsOut>(`/api/tournaments/${slug}/standings`) });

export const useMyBrackets = (tid: string | undefined) =>
  useQuery({
    queryKey: keys.brackets(tid ?? ""),
    queryFn: () => api.get<BracketOut[]>(`/api/brackets?tournament_id=${tid}`),
    enabled: !!tid,
  });

export const useBracket = (id: string | undefined) =>
  useQuery({
    queryKey: keys.bracket(id ?? ""),
    queryFn: () => api.get<BracketOut>(`/api/brackets/${id}`),
    enabled: !!id,
  });

export const useBriefing = (fixtureId: string | undefined) =>
  useQuery({
    queryKey: keys.briefing(fixtureId ?? ""),
    queryFn: () => api.get<BriefingOut>(`/api/fixtures/${fixtureId}/briefing?type=pre_match`),
    enabled: !!fixtureId,
    staleTime: Infinity,
  });

export const useLeaderboard = (id: string | undefined) =>
  useQuery({
    queryKey: keys.leaderboard(id ?? ""),
    queryFn: () => api.get<LeaderboardOut>(`/api/leagues/${id}/leaderboard`),
    enabled: !!id,
  });

export function useCreateBracket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { tournament_id: string; name: string }) =>
      api.post<BracketOut>("/api/brackets", b),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: keys.brackets(v.tournament_id) }),
  });
}

export function useSavePicks(bracketId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (picks: unknown[]) =>
      api.patch<BracketOut>(`/api/brackets/${bracketId}/picks`, { picks }),
    onSuccess: (d) => qc.setQueryData(keys.bracket(bracketId), d),
  });
}

export function useSubmitBracket(bracketId: string) {
  return useMutation({
    mutationFn: () => api.post<InterruptOut | BracketOut>(`/api/brackets/${bracketId}/submit`),
  });
}

export function useConfirmSubmit(bracketId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (approved: boolean) =>
      api.post<BracketOut>(`/api/brackets/${bracketId}/submit/confirm`, { approved }),
    onSuccess: (d) => qc.setQueryData(keys.bracket(bracketId), d),
  });
}

export function useCreateLeague() {
  return useMutation({
    mutationFn: (b: { tournament_id: string; name: string }) =>
      api.post<LeagueOut>("/api/leagues", b),
  });
}

export function useJoinLeague() {
  return useMutation({
    mutationFn: (b: { invite_code: string; bracket_id: string }) =>
      api.post<LeagueOut>("/api/leagues/join", b),
  });
}

// Returns the user's bracket for a tournament, creating one if none exists.
export function useEnsureBracket(tournamentId: string | undefined) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: ["ensure-bracket", tournamentId ?? ""],
    enabled: !!tournamentId,
    staleTime: Infinity,
    queryFn: async () => {
      const existing = await api.get<BracketOut[]>(`/api/brackets?tournament_id=${tournamentId}`);
      const bracket = existing[0] ?? (await api.post<BracketOut>("/api/brackets", {
        tournament_id: tournamentId,
        name: "My Bracket",
      }));
      qc.setQueryData(keys.bracket(bracket.id), bracket);
      return bracket;
    },
  });
}
