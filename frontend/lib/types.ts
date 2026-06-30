// Mirrors the backend *Out schemas (canonical-spec §6).

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
  auth_provider: string;
  favorite_team_ids: string[];
}

export interface TeamOut {
  id?: string | null;
  name: string;
  short_name?: string | null;
  country_code?: string | null;
  crest_url?: string | null;
}

export interface ScoreOut {
  home?: number | null;
  away?: number | null;
}

export interface Stage {
  key: string;
  name: string;
  order: number;
}

export interface TournamentOut {
  id: string;
  slug: string;
  name: string;
  status: string;
  start_date?: string | null;
  end_date?: string | null;
  format_config: { stages?: Stage[]; [k: string]: unknown };
  scoring_config: Record<string, unknown>;
}

export interface FixtureOut {
  id: string;
  stage?: string | null;
  round_key?: string | null;
  group_label?: string | null;
  home?: TeamOut | null;
  away?: TeamOut | null;
  home_placeholder?: string | null;
  away_placeholder?: string | null;
  kickoff_at?: string | null;
  status: string;
  score: ScoreOut;
  venue?: string | null;
}

export interface StandingRowOut {
  rank?: number | null;
  team: string;
  played: number;
  win: number;
  draw: number;
  loss: number;
  goals_for: number;
  goals_against: number;
  points: number;
}

export interface GroupTableOut {
  group: string;
  rows: StandingRowOut[];
}

export interface StandingsOut {
  groups: GroupTableOut[];
}

export interface PickOut {
  id: string;
  fixture_id?: string | null;
  round_key: string;
  pick_type: string;
  predicted_winner_team_id?: string | null;
  predicted_home_score?: number | null;
  predicted_away_score?: number | null;
  predicted_team_id?: string | null;
  points_awarded?: number | null;
  is_correct?: boolean | null;
}

export interface BracketOut {
  id: string;
  tournament_id: string;
  name: string;
  status: string;
  total_score: number;
  picks: PickOut[];
}

export interface InterruptOut {
  interrupt: { id: string; summary: string };
}

export interface BriefingOut {
  id: string;
  fixture_id: string;
  type: string;
  status: string;
  content?: string | null;
  content_format: string;
  model?: string | null;
  generated_at?: string | null;
}

export interface LeagueOut {
  id: string;
  name: string;
  invite_code: string;
  tournament_id: string;
  member_count: number;
  scoring_config?: Record<string, unknown> | null;
}

export interface LeaderboardRow {
  user_id: string;
  display_name: string;
  bracket_id?: string | null;
  total_score: number;
  rank: number;
}

export interface LeaderboardOut {
  league_id: string;
  rows: LeaderboardRow[];
}

export interface LiveEvent {
  minute?: number | null;
  extra?: number | null;
  type: string;
  detail?: string | null;
  team?: string | null;
  player?: string | null;
}

export interface LiveScore {
  status: string;
  minute?: number | null;
  home?: number | null;
  away?: number | null;
}
