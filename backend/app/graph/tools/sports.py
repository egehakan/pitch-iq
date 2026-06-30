"""Sports Q&A tools — bound to the qa_agent ReAct loop.

Each tool depends ONLY on the SportsDataProvider Protocol, reached via the run
context (runtime.context.sports). Tools resolve team names against the live fixture
list so the agent can ask in plain language. They never fabricate: if the provider
returns nothing, the tool says so. (canonical-spec §3.2)
"""
from __future__ import annotations

from langchain.tools import tool
from langgraph.runtime import get_runtime

from app.graph.state import CompanionContext
from app.providers.base import (
    Fixture,
    SportsDataProvider,
    TeamRef,
    TournamentRef,
)


def _ctx() -> CompanionContext:
    return get_runtime(CompanionContext).context


def _sports() -> SportsDataProvider:
    return _ctx().sports


def _tref() -> TournamentRef:
    extras = _ctx().extras or {}
    return extras.get("tournament_ref") or TournamentRef(
        provider="api-football", league="1", season="2026"
    )


def _norm(s: str) -> str:
    return (s or "").strip().lower()


async def _all_fixtures() -> list[Fixture]:
    try:
        return await _sports().list_fixtures(_tref())
    except Exception:
        return []


def _match_team(fx: Fixture, name: str) -> bool:
    n = _norm(name)
    for t in (fx.home, fx.away):
        if t and (n in _norm(t.name) or _norm(t.name) in n):
            return True
    return bool(fx.home_placeholder and n in _norm(fx.home_placeholder)) or bool(
        fx.away_placeholder and n in _norm(fx.away_placeholder)
    )


def _fixture_score(fx: Fixture, query: str) -> int:
    """How many of this fixture's team names are mentioned in the query (0/1/2)."""
    q = _norm(query)
    score = 0
    for t in (fx.home, fx.away):
        if t and t.name and _norm(t.name) in q:
            score += 1
    return score


_LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P"}
_FINISHED_STATUSES = {"FT", "AET", "PEN"}


def _status_rank(status: str) -> int:
    """Live matches are most relevant, then just-played, then upcoming."""
    if status in _LIVE_STATUSES:
        return 3
    if status in _FINISHED_STATUSES:
        return 2
    return 1


def _rank_fixtures(fixtures: list[Fixture], query: str) -> list[Fixture]:
    """Rank fixtures by team-name-in-query count (a 'A vs B' query → the A-vs-B match first),
    then by relevance: live > finished > upcoming, then most recent kickoff. So a single team
    name resolves to their live or just-played match, not a far-future fixture."""
    scored = [(_fixture_score(f, query), f) for f in fixtures]
    hits = [(s, f) for s, f in scored if s > 0]
    if not hits:
        return []
    hits.sort(
        key=lambda sf: (
            -sf[0],
            -_status_rank(sf[1].status),
            -(sf[1].kickoff.timestamp() if sf[1].kickoff else 0),
        )
    )
    return [f for _, f in hits]


def _fx_summary(fx: Fixture) -> str:
    h = fx.home.name if fx.home else (fx.home_placeholder or "TBD")
    a = fx.away.name if fx.away else (fx.away_placeholder or "TBD")
    sc = ""
    if fx.score.home is not None and fx.score.away is not None:
        sc = f" — {fx.score.home}-{fx.score.away}"
    when = fx.kickoff.isoformat() if fx.kickoff else "TBD"
    return f"{h} vs {a}{sc} [{fx.status}] {fx.round_key or fx.stage or ''} kickoff={when} (id={fx.ref.id})"


@tool
async def get_fixture(query: str) -> str:
    """Find a match and its result/score. Pass one team ("Argentina") or two teams
    ("Argentina vs France") — a two-team query returns the specific match between them.
    Returns teams, round, kickoff, status and score. Use this for "what happened in X vs Y"."""
    fixtures = await _all_fixtures()
    if not fixtures:
        return "No fixtures available from the data provider right now."
    q = _norm(query)
    if q in ("live", "now", "today"):
        hits = [f for f in fixtures if f.status in {"1H", "HT", "2H", "ET", "BT", "P"}]
        hits = hits or fixtures[:6]
    else:
        hits = _rank_fixtures(fixtures, query) or [f for f in fixtures if _match_team(f, query)]
    if not hits:
        return f"No fixture found matching '{query}'."
    return "\n".join(_fx_summary(f) for f in hits[:6])


@tool
async def get_live_match_state(team: str) -> str:
    """Get the state (minute/score) and the event timeline (goals, cards, subs) for a match.
    Pass one or two team names; returns the most relevant match's events."""
    fixtures = await _all_fixtures()
    hits = _rank_fixtures(fixtures, team) or [f for f in fixtures if _match_team(f, team)]
    if not hits:
        return f"No match found for '{team}'."
    fx = hits[0]
    h = fx.home.name if fx.home else (fx.home_placeholder or "?")
    a = fx.away.name if fx.away else (fx.away_placeholder or "?")
    # the fixture from list_fixtures carries the authoritative score + status
    live = None
    try:
        live = await _sports().get_live_state(fx.ref)
    except Exception:
        live = None
    status = fx.status
    home_score = fx.score.home if fx.score.home is not None else (live.score.home if live else None)
    away_score = fx.score.away if fx.score.away is not None else (live.score.away if live else None)
    finished = status in _FINISHED_STATUSES
    is_live = status in _LIVE_STATUSES
    if finished:
        state = f"finished {home_score}-{away_score}" + (" (after penalties)" if status == "PEN" else "")
    elif is_live:
        minute = (live.minute if live else None) or fx.elapsed
        state = f"live, {minute or '?'}', {home_score or 0}-{away_score or 0}"
    else:
        state = "not started yet"
    head = f"{h} vs {a} [{fx.round_key or ''}] — {state}."
    evs = [
        f"  {e.minute or '?'}'" + (f"+{e.extra}" if e.extra else "")
        + f" {e.type} {e.detail or ''} ({e.team or ''} {e.player or ''})".rstrip()
        for e in (live.events[-10:] if live else [])
    ]
    if evs:
        return head + "\nKey events:\n" + "\n".join(evs)
    return head + ("\n(Detailed event timeline isn't available for this match.)" if finished or is_live else "")


@tool
async def get_lineups(team: str) -> str:
    """Get the starting XI, formation and bench for the match involving a given team (published ~1h pre-kickoff)."""
    fixtures = await _all_fixtures()
    hits = [f for f in fixtures if _match_team(f, team)]
    if not hits:
        return f"No match found for '{team}'."
    try:
        lu = await _sports().get_lineups(hits[0].ref)
    except Exception as e:
        return f"Could not fetch lineups: {e}"
    out = []
    for side in (lu.home, lu.away):
        if not side or not side.starting_xi:
            continue
        names = ", ".join(p.name for p in side.starting_xi)
        out.append(f"{side.team or 'Team'} ({side.formation or '?'}): {names}")
    return "\n".join(out) if out else "Lineups not yet published for this match."


@tool
async def get_standings(group: str = "") -> str:
    """Get group/standings tables for the tournament. Optionally filter to a single group label (e.g. 'A')."""
    try:
        st = await _sports().get_standings(_tref())
    except Exception as e:
        return f"Could not fetch standings: {e}"
    if not st.groups:
        return "No standings available."
    groups = st.groups
    if group:
        g = _norm(group)
        groups = [grp for grp in st.groups if _norm(grp.group).endswith(g)] or st.groups
    out = []
    for grp in groups[:12]:
        rows = "\n".join(
            f"  {r.rank or i+1}. {r.team} — {r.points}pts ({r.win}W {r.draw}D {r.loss}L, GF{r.goals_for}/GA{r.goals_against})"
            for i, r in enumerate(grp.rows)
        )
        out.append(f"Group {grp.group}:\n{rows}")
    return "\n".join(out)


@tool
async def get_head_to_head(team_a: str, team_b: str) -> str:
    """Get the recent head-to-head meeting history between two teams."""
    try:
        h2h = await _sports().get_head_to_head(
            TeamRef(provider="api-football", id="0", name=team_a),
            TeamRef(provider="api-football", id="0", name=team_b),
        )
    except Exception as e:
        return f"Could not fetch head-to-head: {e}"
    if not h2h.meetings:
        return f"No recent head-to-head record between {team_a} and {team_b}."
    lines = [
        f"  {(m.date.date().isoformat() if m.date else '?')}: {m.home or '?'} {m.score.home or 0}-{m.score.away or 0} {m.away or '?'}"
        for m in h2h.meetings[:8]
    ]
    return f"Head-to-head {team_a} vs {team_b}:\n" + "\n".join(lines)


@tool
async def get_team_form(team: str, n: int = 5) -> str:
    """Get a team's recent form (last-N results, W/D/L string)."""
    try:
        form = await _sports().get_team_form(TeamRef(provider="api-football", id="0", name=team), n)
    except Exception as e:
        return f"Could not fetch form: {e}"
    if not form.last_n:
        return f"No recent form data for {team}."
    lines = [
        f"  {(r.date.date().isoformat() if r.date else '?')}: {r.result or '?'} {r.score.home or 0}-{r.score.away or 0} vs {r.opponent or '?'}"
        for r in form.last_n[:n]
    ]
    return f"{team} form ({form.wdl}):\n" + "\n".join(lines)


SPORTS_TOOLS = [
    get_fixture,
    get_live_match_state,
    get_lineups,
    get_standings,
    get_head_to_head,
    get_team_form,
]
