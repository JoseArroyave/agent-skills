# Football Betting Analysis

Pre-match football analysis in 8 layers. Receives a natural language query, discovers the match via FlashScore MCP (RapidAPI Hub), gathers data, and produces a structured report with probabilistic language.

## System Requirements

This skill is an AI agent workflow and requires:

### Required Access

- **FlashScore MCP** (RapidAPI Hub — FlashScore V2 API)
- No API token required (authenticates via MCP server)

### Environment Setup

The MCP server must be configured with access to RapidAPI Hub. Refer to your MCP client documentation for setup instructions.

## Architecture

```
User (natural language query)
    │
    ▼
Agent parses query
    │
    ▼
Phase 1: Match Discovery
    Get_Matches_by_day / Get_Matches_by_date
    │
    ▼
Phase 2: Data Gathering
    ┌─ OBLIGATORIA PARA INICIAR:
    │   Get_Match_Details?match_id=X → evento + odds
    └─ OBLIGATORIAS DE INTENTO:
        Get_Match_H2H?match_id=X              → Head-to-head
        Get_Match_Stats?match_id=X             → stats (corners, tiros, posesión, tarjetas, xG)
        Get_Match_Player_Stats?match_id=X     → stats por jugador
        Get_Match_Commentary?match_id=X        → commentary
        Get_Team_Results?team_id=X            → historial de resultados
        Get_Tournament_Standings?tournament_id=X → posición en torneo
    │
    ▼
8-Layer Analysis Pipeline
    ├── Layer 1 — Base Context (market odds, implied probabilities)
    ├── Layer 2 — Team Descriptive (form, H2H, averages)
    ├── Layer 3 — Player Descriptive (direct stats, rankings)
    ├── Layer 4 — Composite Indicators (gaps, risks)
    ├── Layer 5 — Diagnostic (trends, contradictions, commentary)
    ├── Layer 6 — Signal Weighting (strong/moderate/weak)
    ├── Layer 7 — Predictive (odds-driven probabilities)
    └── Layer 8 — Prescriptive (best-supported markets)
    │
    ▼
Structured Report + Confidence Level
```

## Core Behavior

- The skill only analyzes **pre-match** events (`status = notstarted`).
- If a match is `inprogress` or `finished`, the skill declines with a user message.
- **No external data sources** — only FlashScore MCP is used.
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
2. Discovers the match via FlashScore MCP (`Get_Matches_by_day` / `Get_Matches_by_date`)
3. Gathers all available data (event, odds, stats, player stats, commentary, team results, standings)
4. Runs the 8-layer analysis pipeline
5. Produces a structured report with confidence level

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

## API Endpoints Used (FlashScore MCP)

```
Get_Matches_by_day / Get_Matches_by_date  → match discovery
Get_Match_Details?match_id=X              → evento + odds
Get_Match_H2H?match_id=X                  → Head-to-head
Get_Match_Stats?match_id=X                 → stats del partido
Get_Match_Player_Stats?match_id=X         → stats por jugador
Get_Match_Commentary?match_id=X            → commentary
Get_Team_Results?team_id=X               → historial de resultados
Get_Tournament_Standings?tournament_id=X → posición en torneo
```

### Endpoint Priority

| Priority | Endpoints | Behavior on failure |
|---|---|---|
| **Obligatoria para iniciar** | `Get_Match_Details` | Analysis not viable |
| **Obligatorias de intento** | `Get_Match_H2H`, `Get_Match_Stats`, `Get_Match_Player_Stats`, `Get_Match_Commentary`, `Get_Team_Results`, `Get_Tournament_Standings` | `[N/A]` + degrade only affected layer |

### What Does NOT Exist in FlashScore

| Non-existent data | Consequence |
|---|---|
| `GET /api/events/?team=X` | No direct "last 10 matches of team" query. Use `Get_Team_Results`. |
| Confirmed pre-match lineups | `Get_Match_Player_Stats` may be empty pre-match. Do not invent. |
| Historical injury data | Not available. Do not invent. |
| Pre-match H2H confirmations | `Get_Match_H2H` may return null. Mark `[N/A]`. |

## Source Tags

Every data point in the analysis is tagged with its source:

| Tag | Meaning |
|-----|---------|
| `[API]` | Direct from a FlashScore MCP endpoint |
| `[ODDS]` | Calculated from market odds |
| `[IND]` | Indicator derived from API data (not from odds) |
| `[N/A]` | Not available in FlashScore MCP |

## The 8 Layers

### Layer 1 — Base Context
Market odds → implied probabilities. Indicators vs market alignment. No invented percentages.

### Layer 2 — Team Descriptive
Recent form (W/D/L), points, goals scored/conceded, Over 2.5/BTTS frequency. Home/away split. H2H history.

### Layer 3 — Player Descriptive
Top attackers per team from direct stats (goals, assists, shots, key_passes). Rankings by metric. No composite formulas.

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

| Data available | Maximum confidence |
|---|---|
| Event + odds + stats + player-stats + team results + standings | **High** |
| Event + odds + stats (no player-stats) | **Medium-high** |
| Event + odds (no stats) | **Medium** |
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

## Anti-Rationalization Rules

These rules are **mandatory**. Never:

- Invent data when `[N/A]` — if player-stats is missing, say so
- Use Bzzoiro, SofaScore, Transfermarkt, or any source other than FlashScore MCP
- Build a heuristic model to replace the odds-driven architecture
- Say "will win", "it's certain", "over 2.5 is guaranteed"
- Assign percentage probabilities to indicators (Layer 7 probabilities come from odds only)
- Use commentary as a primary signal (only valid if corroborated by other layers)
- Analyze a match that has already started or finished
- Calculate composite scores with weights (0.3, 0.5, etc.) in Layer 3 — use direct data + rankings