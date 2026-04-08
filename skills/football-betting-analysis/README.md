# Football Betting Analysis

Pre-match football analysis in 8 layers. Receives a natural language query, discovers the match via the Bzzoiro API, gathers data, and produces a structured report with probabilistic language.

## System Requirements

This skill is an AI agent workflow and requires:

### Required Access

- **Bzzoiro API** (`https://sports.bzzoiro.com`)
- **API Token** — stored in environment variable `BZzoiro_TOKEN`

### Environment Setup

```bash
export BZzoiro_TOKEN="your_bzzoiro_api_token"
```

## Architecture

```
User (natural language query)
    │
    ▼
Agent parses query
    │
    ▼
Phase 1: Match Discovery
    GET /api/events/?date_from=X&date_to=Y[&league=Z]
    │
    ▼
Phase 2: Data Gathering
    ├── GET /api/events/{id}/          → event + odds + form + H2H
    ├── GET /api/predictions/?date_from=X&date_to=Y&league=Z
    └── GET /api/player-stats/?event={id}
    │
    ▼
8-Layer Analysis Pipeline
    ├── Layer 1 — Base Context (odds, ML)
    ├── Layer 2 — Team Descriptive (form, H2H)
    ├── Layer 3 — Player Descriptive (impact metrics)
    ├── Layer 4 — Composite Indicators (gaps, risks)
    ├── Layer 5 — Diagnostic (trends, contradictions)
    ├── Layer 6 — Signal Weighting (strong/moderate/weak)
    ├── Layer 7 — Predictive (probabilities, scoreline)
    └── Layer 8 — Prescriptive (best-supported markets)
    │
    ▼
Structured Report + Confidence Level
    │
    ▼
Saved to ./claude/skills/football-betting-analysis/<league>/<file>.txt
```

## Core Behavior

- The skill only analyzes **pre-match** events (`status = notstarted`).
- If a match is `inprogress` or `finished`, the skill declines with a user message.
- **No external data sources** — only the Bzzoiro API is used.
- No invented data. Missing data is marked `[N/A]` with a brief explanation.
- Probabilistic language only: "could", "signal", "suggests". Never: "will win", "it's certain", "over 2.5 is guaranteed".

## When To Use

Use this skill when:

- The user requests analysis of a specific football match
- The query includes teams, date, and optionally the competition
- Pre-match context, form, players, ML predictions, and recommendations are needed
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
2. Discovers the match via the Bzzoiro API
3. Gathers all available data (event, odds, form, predictions, player stats)
4. Runs the 8-layer analysis pipeline
5. Produces a structured report with confidence level
6. Saves the analysis to disk

## Input (Natural Language Query Examples)

```
"Analyze Barcelona vs Real Madrid for this weekend"
"What do you think about Atletico vs Sevilla on Friday?"
"Lens vs PSG — any good markets?"
"Leverkusen next match"
```

### Query Parsing

| Field | Description |
|-------|-------------|
| `home_team` | First team mentioned |
| `away_team` | Second team mentioned (or null if only one) |
| `date_from` | Start of date range (ISO 8601) |
| `date_to` | End of date range (ISO 8601) |
| `league` | Competition mentioned (or null) |

**Date shortcuts:**
- "hoy" / "today" → date_from = today, date_to = today
- "mañana" / "tomorrow" → date_from = tomorrow, date_to = tomorrow
- "este finde" / "this weekend" → date_from = friday, date_to = sunday
- "esta semana" / "this week" → date_from = monday, date_to = sunday

## API Endpoints Used

```
GET /api/events/?date_from=X&date_to=Y[&league=Z]  → match discovery
GET /api/events/{id}/                              → event + odds + form + H2H
GET /api/predictions/?date_from=X&date_to=Y&league=Z → ML prediction lookup
GET /api/player-stats/?event={id}                  → player statistics
GET /api/teams/{id}/                               → team metadata
GET /api/leagues/                                  → competition list
```

### What Does NOT Exist in the Bzzoiro API

| Non-existent endpoint | Consequence |
|---|---|
| `GET /api/events/?team=X` | No direct "last 10 matches of Barcelona" query. Form comes embedded in the event object. |
| `GET /api/predictions/{event_id}/` | Prediction ID ≠ event ID. Must search by embedded `event.id`. |
| Corners endpoint | Not provided. Do not mention. |
| Pre-match lineups | `lineups` is `null` pre-match. Do not use. |
| Injury history | Not available. Do not invent. |

## Source Tags

Every data point in the analysis is tagged with its source:

| Tag | Meaning |
|-----|---------|
| `[API]` | Direct from a Bzzoiro API endpoint |
| `[ML]` | From the ML prediction model (`/api/predictions/`) |
| `[ODDS]` | Calculated from market odds |
| `[IND]` | Composite indicator calculated from API data |
| `[N/A]` | Not available in the API |

## The 8 Layers

### Layer 1 — Base Context
Market odds → implied probabilities. ML prediction (if available). Do they agree?

### Layer 2 — Team Descriptive
Recent form (W/D/L), points, goals scored/conceded, xG, Over 2.5/BTTS frequency. Home/away split. H2H history.

### Layer 3 — Player Descriptive
Top 3 attackers per team by offensive impact. Creation and defense metrics. Disciplinary risk. Over-reliance on a single player.

### Layer 4 — Composite Indicators
Offensive advantage, defensive fragility, form gap, home/away gap, Over/BTTS risk, volatility, discipline index, market-model coherence.

### Layer 5 — Diagnostic
Are results backed by xG? Is defense conceding by merit or weak opponents? Is Over 2.5 from volume or defensive chaos? Sustainable trend or noise?

### Layer 6 — Signal Weighting
Classifies all signals as **strong** (xG, consistency N≥5, market-ML alignment), **moderate** (N=3-4, H2H), or **weak** (N<3, contradictions).

### Layer 7 — Predictive
Combined probabilities from ML + indicators. Expected goals per team. Most likely scoreline. Match type (closed/open/defensive/competitive). Confidence level.

### Layer 8 — Prescriptive
Top 3-5 strongest signals. 2-3 alerts. Markets with multi-layer support. Markets without support (briefly explained).

## Confidence Levels

| Data available | Maximum confidence |
|---|---|
| Event + odds + ML + player-stats + form | **High** |
| Event + odds + ML (no player-stats) | **Medium-high** |
| Event + ML (no odds) | **Medium** |
| Event + odds (no ML) | **Medium** |
| Event only | **Low** |
| No event | **Analysis not viable** |

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

## Data Storage

Analysis files are saved to:
```
./claude/skills/football-betting-analysis/<league_name>/<DD_MM_YYYY> [Home] vs [Away] [Jornada_X].txt
```

Example:
```
./claude/skills/football-betting-analysis/Champions League 25-26/08_04_2026 Barcelona vs Real Madrid Jornada_X.txt
```

## Anti-Rationalization Rules

These rules are **mandatory**. Never:

- Invent data when `[N/A]` — if player-stats is missing, say so
- Use SofaScore, Flashscore, Transfermarkt, or any source other than Bzzoiro API
- Build a heuristic model to replace the ML prediction
- Say "will win", "it's certain", "over 2.5 is guaranteed"
- Skip contradictions — if market and ML favor different sides, say so explicitly
- Leave a section blank — if data is missing, write `[N/A]` with brief reason
- Analyze a match that has already started or finished

## Design Goals

- Single authoritative source (Bzzoiro API only)
- No data fabrication
- Probabilistic language at all times
- Graceful degradation when data is missing
- Transparent confidence levels
- Structured, reproducible output
