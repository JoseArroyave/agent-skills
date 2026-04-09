# Football Betting Analysis

Pre-match football analysis in 8 layers. Receives a natural language query, discovers the match via FlashScore MCP, executes `build_match_context.py` to get a normalized JSON context, and produces a structured report with probabilistic language.

**Architecture shift:** The model no longer calls FlashScore endpoints directly for match data. It uses MCP only for match discovery, and delegates all data gathering to `build_match_context.py`, which returns a single normalized `final_context` JSON.

## System Requirements

### Required Access

- **FlashScore MCP** — [FlashScore V2 API on RapidAPI](https://rapidapi.com/rapidapi-org1-rapidapi-org-default/api/flashscore4)
- `build_match_context.py` script (bundled with this skill)
- `RAPIDAPI_KEY` stored in `~/.claude/settings.json` or `~/.claude/settings.local.json`

### Environment Setup

1. Configure FlashScore MCP with your RapidAPI credentials ([FlashScore V2 API](https://rapidapi.com/rapidapi-org1-rapidapi-org-default/api/flashscore4)).
2. Ensure `RAPIDAPI_KEY` is present in your Claude settings file.
3. The script reads the key automatically — no environment variables needed.

## Architecture

```
User (natural language query)
    │
    ▼
Agent parses query
    │
    ▼
Phase 1: Match Discovery (MCP direct)
    teams.csv lookup → Get_Team_Fixtures → Get_Team_Results (fallback)
    → event_id, home_team_id, away_team_id
    │
    ▼
Phase 2: Preprocessing (build_match_context.py)
    Receives: event_id, home_team_id, away_team_id
    Internally calls all FlashScore endpoints:
      - fetch_match_details()
      - fetch_match_odds()
      - fetch_team_results() (x2)
      - fetch_match_stats()
      - fetch_match_player_stats()
      - fetch_match_lineups()
      - fetch_match_summary()
      - fetch_match_commentary()
      - fetch_tournament_standings()
      - fetch_match_standings_form()
      - fetch_match_standings_overunder()
      - fetch_match_top_scorers()
      - fetch_tournament_top_scorers()
    Returns: single final_context JSON
    │
    ▼
8-Layer Analysis Pipeline (model only reads final_context)
    ├── Layer 1 — Base Context (market odds, implied probabilities)
    ├── Layer 2 — Team Descriptive (form, H2H, averages)
    ├── Layer 3 — Protagonists (player stats, missing players)
    ├── Layer 4 — Composite Indicators (gaps, risks)
    ├── Layer 5 — Diagnostic (trends, contradictions)
    ├── Layer 6 — Signal Weighting (strong/moderate/weak)
    ├── Layer 7 — Predictive (odds-driven probabilities)
    └── Layer 8 — Prescriptive (best-supported markets)
    │
    ▼
Structured Report + Confidence Level
```

**Key constraint:** After Phase 1, no more MCP calls for match data. The model receives a single JSON and only redacta (writes the analysis) from it.

## Core Behavior

- The skill only analyzes **pre-match** events (`status = notstarted`).
- If a match is `inprogress` or `finished`, the skill declines with a user message.
- **No external data sources** — only FlashScore via `build_match_context.py`.
- No invented data. Missing data is marked `[N/A]` with a brief explanation.
- Probabilities **only from odds** — indicators modulate confidence, never generate percentages.
- Probabilistic language only: "could", "signal", "suggests". Never: "will win", "it's certain", "over 2.5 is guaranteed".

## When To Use

Use this skill when:

- The user requests analysis of a specific football match
- The query includes teams, date, and optionally the competition
- Pre-match context, form, players, indicators, and recommendations are needed
- The match has not started yet

## When NOT To Use

Do not use this skill when:

- The match status is `inprogress` or `finished` → respond: "That match already started/finished. Wait for an upcoming one."
- The query is about a tournament or team without a specific match → not applicable. Offer to search for upcoming matches of that team.
- The user asks for in-play analysis → this skill is pre-match only.

## Installation

From the root repository:

```bash
npx skills add JoseArroyave/agent-skills --skill football-betting-analysis
```

## Usage (Agent Invocation)

The skill is invoked automatically when the user requests pre-match football analysis. The agent:

1. Parses the natural language query into structured fields
2. **Phase 1:** Looks up team IDs from `teams.csv`, then discovers the match via FlashScore MCP (`Get_Team_Fixtures` → `Get_Team_Results` fallback) → extracts `event_id`, `home_team_id`, `away_team_id`
3. **Phase 2:** Executes `build_match_context.py` with those three IDs → receives `final_context` JSON
4. Runs the 8-layer analysis pipeline using only the data in `final_context`
5. Produces a structured report with confidence level

## Input (Natural Language Query Examples)

```
"Analyze Barcelona vs Real Madrid for this weekend"
"What do you think about Atletico vs Sevilla on Friday?"
"Lens vs PSG — any good markets?"
"Leverkusen next match"
```

### Query Parsing

| Field       | Description                                 |
| ----------- | ------------------------------------------- |
| `home_team` | First team mentioned                        |
| `away_team` | Second team mentioned (or null if only one) |
| `date_from` | Start of date range (ISO 8601)              |
| `date_to`   | End of date range (ISO 8601)                |
| `league`    | Competition mentioned (or null)             |

**Date shortcuts:**

- "hoy" / "today" → date_from = today, date_to = today
- "mañana" / "tomorrow" → date_from = tomorrow, date_to = tomorrow
- "este finde" / "this weekend" → date_from = friday, date_to = sunday
- "esta semana" / "this week" → date_from = monday, date_to = sunday

## Data Flow — MCP vs Script

| What            | How                                                               |
| --------------- | ----------------------------------------------------------------- |
| Match discovery | `teams.csv` → `Get_Team_Fixtures` → `Get_Team_Results` via MCP       |
| All other data  | `build_match_context.py` (internal API calls)                        |

**The model must not call any MCP endpoint after receiving `final_context`.**

## Endpoints Consumed by `build_match_context.py`

These are called **internally by the script**, not by the model:

```
fetch_match_details()       → /matches/details
fetch_match_odds()         → /matches/odds
fetch_team_results()       → /teams/results (home + away)
fetch_match_stats()         → /matches/match/stats
fetch_match_player_stats() → /matches/match/player-stats
fetch_match_lineups()       → /matches/match/lineups
fetch_match_summary()      → /matches/match/summary
fetch_match_commentary()   → /matches/match/commentary
fetch_tournament_standings()   → /tournaments/standings
fetch_match_standings_form()    → /matches/standings/form
fetch_match_standings_overunder() → /matches/standings/over-under
fetch_match_top_scorers()  → /matches/standings/top-scorers
fetch_tournament_top_scorers() → /tournaments/standings/top-scorers
```

## `final_context` Output Schema

The script returns a single JSON with this structure:

```json
{
  "meta": { "event_id", "home_team_id", "away_team_id", "generated_at" },
  "match": {
    "event_id", "status",
    "home_team": { "id", "name", "event_participant_id" },
    "away_team": { "id", "name", "event_participant_id" },
    "tournament": { "id", "stage_id", "name" },
    "country", "referee", "timestamp", "datetime",
    "scores": { "home", "away", "home_total", "away_total", ... }
  },
  "odds": {
    "available_markets": [],
    "odds_home", "odds_draw", "odds_away",
    "odds_over_25", "odds_under_25",
    "odds_btts_yes", "odds_btts_no",
    "warnings": []
  },
  "implied_probs": { "prob_home", "prob_draw", "prob_away", "prob_over_25", "prob_btts_yes" },
  "h2h": {
    "records": [{ "match_id", "timestamp", "home_score", "away_score", "home_team", "away_team", "tournament_id", "tournament_name" }],
    "summary": { "total_matches", "home_wins", "draws", "away_wins", "avg_goals" },
    "warnings": []
  },
  "team_home_results": {
    "matches": [{ ... }],
    "form": { "last_n", "form_string", "points", "gf_avg", "gc_avg", "over_25_freq", "btts_freq", "home_ppg", "away_ppg", ... },
    "warnings": null
  },
  "team_away_results": { "matches": [...], "form": {...}, "warnings": null },
  "match_stats": {
    "stats": [{ "name", "home_team", "away_team", "home_pct", "away_pct" }],
    "possession": { "home", "away" },
    "total_shots": { "home", "away" },
    "shots_on_target": { "home", "away" },
    "corners": { "home", "away" },
    "yellow_cards": { "home", "away" },
    "red_cards": { "home", "away" },
    "xg": { "home", "away" },
    "xgotal": { "home", "away" },
    "passes": { "home": { "accuracy_pct", "completed" }, "away": {...} },
    "warnings": null
  },
  "player_stats": {
    "home_players": [{ "player_id", "name", "short_name", "position", "in_base_lineup", "goals", "assists", "shots", "shots_on_target", "key_passes", ... }],
    "away_players": [...],
    "top_scorers_home", "top_scorers_away": [...],
    "top_assists_home", "top_assists_away": [...],
    "top_shots_home", "top_shots_away": [...],
    "top_key_passes_home", "top_key_passes_away": [...],
    "warnings": null
  },
  "lineups": {
    "home": { "formation", "lineup_count", "missing_players": [{ "name", "player_id", "reason", "country" }], "unsure_missing": [...] },
    "away": { "formation", "lineup_count", "missing_players": [...], "unsure_missing": [...] },
    "warnings": null
  },
  "summary": {
    "events": [{ "minutes", "team", "type", "description" }],
    "goals_home", "goals_away",
    "warnings": null
  },
  "commentary": [...] | null,
  "standings": {
    "teams": { [team_id]: { "position", "name", "points", "wins", "draws", "losses", "goals", "goal_difference" } },
    "warnings": null
  },
  "overunder_standings": {
    "teams": { [team_id]: { "over", "under", "average_goals" } },
    "warnings": null
  },
  "form_standings": {
    "teams": { [team_id]: { "points", "form_string" } },
    "warnings": null
  },
  "top_scorers": {
    "home_scorers": [{ "name", "player_id", "team", "goals", "assists" }],
    "away_scorers": [...],
    "warnings": null
  },
  "tournament_top_scorers": {
    "home_scorers": [...],
    "away_scorers": [...],
    "warnings": null
  },
  "indicators": {
    "offensive_dependency": [{ "side", "player", "team_goals_in_sample", "player_goals", "pct_team_goals", "dependency" }],
    "sample_stability": { "home": { "n", "stability" }, "away": { "n", "stability" } }
  },
  "warnings": []
}
```

## Source Tags

Every data point in the analysis is tagged with its source:

| Tag      | Meaning                                                             |
| -------- | ------------------------------------------------------------------- |
| `[API]`  | Direct from a FlashScore endpoint (via `build_match_context.py`)    |
| `[ODDS]` | Calculated from market odds in `final_context`                      |
| `[IND]`  | Indicator derived from API data (not from odds)                     |
| `[N/A]`  | Not available — marked by the script or absent from `final_context` |

## The 8 Layers

### Layer 1 — Base Context

Market odds → implied probabilities. Indicators vs market alignment. No invented percentages.

### Layer 2 — Team Descriptive

Recent form (W/D/L), points, goals scored/conceded, Over 2.5/BTTS frequency. Home/away split. H2H history (built from team results, not a separate call).

### Layer 3 — Protagonists

Two lanes: **(A)** player stats from `player_stats` in JSON (goals, assists, shots, key_passes); **(B)** `missingPlayers` from `lineups` in JSON. No composite formulas. Rankings by individual metric only.

### Layer 4 — Composite Indicators

Offensive advantage, defensive fragility, form gap, home/away gap, Over/BTTS risk, volatility, discipline index, market-data coherence.

### Layer 5 — Diagnostic

Are results backed by stats? Is defense conceding by merit or weak opponents? Is Over 2.5 from volume or defensive chaos? Commentary corroborated by other layers.

### Layer 6 — Signal Weighting

Classifies all signals as **strong** (consistency N≥5, market-data alignment), **moderate** (N=3-4, H2H), or **weak** (N<3, contradictions).

### Layer 7 — Predictive

Probabilities **only from odds**. Implied probabilities for 1X2, Over 2.5, BTTS. Confidence modulated by indicator alignment. **No invented percentages.**

### Layer 8 — Prescriptive

Top 3-5 strongest signals. 2-3 alerts. Markets with multi-layer support. Markets without support (briefly explained).

## Confidence Levels

| Data available                                                 | Maximum confidence      |
| -------------------------------------------------------------- | ----------------------- |
| Event + odds + stats + player-stats + team results + standings | **High**                |
| Event + odds + stats (no player-stats)                         | **Medium-high**         |
| Event + odds (no stats)                                        | **Medium**              |
| Event only                                                     | **Low**                 |
| No event                                                       | **Analysis not viable** |

## Output Format

```
# [Home] vs [Away] — [Competition] ([Date])

## 1. Context
[...]

## 2. What's Been Happening
[...]

## 3. Protagonists
[...]

## 4. Composite Indicators
[...]

## 5. Why It's Happening
[...]

## 6. Which Signals Weigh More
[...]

## 7. What Could Happen
[...]

## 8. What to Read With Best Support
[...]

---
Confidence: [very low / low / medium / medium-high / high]
```

## Anti-Rationalization Rules

These rules are **mandatory**. Never:

- Invent data when `[N/A]` — if player-stats is missing, say so
- Use Bzzoiro, SofaScore, Transfermarkt, or any source other than FlashScore
- Build a heuristic model to replace the odds-driven architecture
- Say "will win", "it's certain", "over 2.5 is guaranteed"
- Assign percentage probabilities to indicators (Layer 7 probabilities come from odds only)
- Use commentary as a primary signal (only valid if corroborated by other layers)
- Analyze a match that has already started or finished
- Calculate composite scores with weights (0.3, 0.5, etc.) in Layer 3 — use direct data + rankings
- Call MCP endpoints directly after receiving `final_context` — all data must come from the JSON
- Re-interpret or recalculate data already normalized in `final_context`
- Use `Get_Match_H2H`, `Get_Match_Details`, etc. directly — those are called inside `build_match_context.py`

## What Does NOT Exist in FlashScore

| Non-existent data           | Consequence                                                     |
| -------------------------- | --------------------------------------------------------------- |
| Confirmed pre-match lineups | `Get_Match_Lineups` exists but may be empty pre-match. Do not invent. |
| Historical injury data      | Not available. Do not invent.                                   |

## Pipeline Rules (Summary)

```
Phase 1 (MCP direct):
  teams.csv → Get_Team_Fixtures → Get_Team_Results (fallback)
  → Extract: event_id, home_team_id, away_team_id

Phase 2 (build_match_context.py):
  python scripts/build_match_context.py <event_id> <home_team_id> <away_team_id>
  → Returns final_context JSON

NO MCP CALLS AFTER PHASE 1.
NO ENDPOINTS CALLED DIRECTLY BY THE MODEL.
```
