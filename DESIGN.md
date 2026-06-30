# Pitch IQ — Design System

A matchnight broadcast monitor: quiet cool ink, one floodlight accent, live state the only
thing that pulses. Data set like a broadcast lower-third. The agent's run is the signature.

## Color (OKLCH; never #000/#fff; neutrals tinted cool ink, hue 264)
| Role | OKLCH | Use |
|---|---|---|
| `--ink` (bg) | `0.165 0.012 264` | app background |
| `--surface` | `0.205 0.014 264` | panels, rails |
| `--surface-2` | `0.245 0.016 264` | raised cards, inputs |
| `--line` | `0.305 0.014 264` | hairline borders (1px) |
| `--line-strong` | `0.38 0.016 264` | dividers that matter |
| `--text` | `0.95 0.006 264` | primary text |
| `--muted` | `0.66 0.012 264` | secondary text, labels |
| `--faint` | `0.50 0.012 264` | tertiary / disabled |
| `--accent` (floodlight) | `0.80 0.155 68` | the one energy: primary actions, the active agent, key highlights. ≤10% of surface. |
| `--accent-press` | `0.72 0.15 66` | accent active state |
| `--live` (signal) | `0.64 0.225 25` | reserved: LIVE badge + live score pulse ONLY |
| `--good` | `0.74 0.13 150` | correct pick / advanced (state, not brand) |
| `--on-accent` | `0.18 0.02 70` | text on the amber accent |

Color strategy: **Restrained** — tinted ink neutrals + one accent used with discipline,
plus a strictly-reserved live-red. Not Committed; the accent never carries a surface.

## Type
- **Display — Archivo** (variable grotesque). Headings, team names, the wordmark. Tight
  tracking, weights 600–800. The broadcast voice.
- **Body — Inter.** All running text and UI. 14–15px base, 1.5 line-height, cap 70ch.
- **Data — JetBrains Mono.** Scores, clock, probabilities, durations, the agent run trace.
  `font-variant-numeric: tabular-nums`. The terminal voice.
- Scale (ratio ≥1.25): 12 / 13 / 15 / 18 / 22 / 28 / 40 / 56. Hierarchy via size + weight,
  never color alone.

## Layout
- 8px base rhythm; vary deliberately (24 between sections, 12 within, 4 micro). Never the
  same padding everywhere.
- The companion is **chat-led**: a wide primary conversation + a quiet right rail (live
  match + your bracket + next up). The 5-round bracket lives on its own page where it can
  breathe — never crammed into a third of the screen.
- Cards are not the default. Use a full hairline border or a tint, never a side-stripe.
  No nested cards.
- Max content width 1240px; the bracket page goes edge-to-edge with horizontal scroll.

## Signature — the agent run
The chat answer is a *run*, shown the way an analyst shows working: a compact trace under
the question — `routed → [specialist] → tool · tool · tool → answer` — with live status
(running/done), tool durations in mono, and the answer streaming token by token. This is
the one element the product is remembered by. Everything else stays quiet around it.

## Motion
- ease-out-expo / quint only; 120–260ms. No bounce.
- Animate opacity/transform only, never layout. Respect `prefers-reduced-motion`.
- The only ambient motion: the LIVE dot pulse and the streaming caret.

## Icons
Lucide, 1.5px stroke, sized to the text (16/18/20). No emoji anywhere.

## Components
Button (accent / ghost / outline / danger), Field (label + input + hint/error), Badge
(neutral / live / accent / good), Panel (hairline-bordered region with a labelled header),
RunTrace (the agent steps), Scoreboard (broadcast match header), MatchNode + BracketBoard,
Leaderboard. Focus-visible ring in accent on every interactive element.
