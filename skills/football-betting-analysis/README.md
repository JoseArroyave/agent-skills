# football-betting-analysis

Quantitative football betting analysis based on RapidAPI Hub - Free API Live Football Data.

This skill produces analysis based on pure statistical data, crossing domestic league, national cups, European competitions, and individual player form to build a rigorous evaluation of each team and match.

---

## System Requirements

### Required Services

- **RapidAPI Hub — Free API Live Football Data** — available as an MCP server for easier integration:

```json
"RapidAPI Hub - Free API Live Football Data": {
  "command": "npx",
  "args": [
    "mcp-remote",
    "https://mcp.rapidapi.com",
    "--header",
    "x-api-host: free-api-live-football-data.p.rapidapi.com",
    "--header",
    "x-api-key: <api_key>"
  ]
}
```

This MCP provides all the endpoints documented in SKILL.md.

### Rate Limiting

- **1000 requests/hour** — the skill plans calls efficiently by priority

---

## Architecture

```
User
→ Agent
→ football-analysis-engine skill
    ├── Phase 1: Identification (match ID, date/time)
    ├── Phase 2: Match Data (score, stats, events, highlights)
    ├── Phase 3: Global Team Data (squad, top players)
    ├── Phase 4: Standings and League Position
    ├── Phase 5: Additional Competitions
    ├── Phase 6: Recent Form and News
    └── Phase 7: Transfers and Physical Form
    ↓
Agent receives structured analysis (Layers 1-6)
↓
User
```

---

## Core Behavior

- **Global Analysis**: Never limits analysis to a single competition. Crosses league + cup + Europe.
- **Fast Mode** (~25 API calls): For direct day-of queries.
- **Deep Mode** (~80 API calls): For complete analysis of Champions, finals, Derbies.
- **Data Tagged by Confidence**: [API] (direct), [DER] (derived), [INF-M] (medium confidence inference), [INF-B] (low confidence inference), [N/A] (not available).
- **Prediction with Explicit Confidence**: HIGH / MEDIUM / LOW / VERY LOW based on sample size.

---

## Capabilities

### Descriptive Analysis

- Recent form by rolling windows (3, 5, 10 matches)
- Performance by competition (league, cup, Europe)
- Home vs Away performance
- vs Top-10 performance

### Pattern Detection

- Active streaks (wins, Over 2.5, BTTS, clean sheets)
- Sample bias identification
- Instability signals

### Statistical Recommendations

- Over/Under 1.5, 2.5, 3.5 goals
- Both Teams To Score (BTTS)
- Home and Away Clean Sheet
- 1X2 Result
- Corners and Cards
- Player recommendations (goals, assists)

### Data Taxonomy

| Symbol | Type | Definition |
|---------|------|------------|
| `[API]` | Direct data | Literal endpoint response |
| `[DER]` | Derived data | Calculated from [API] (sum, division, average) |
| `[INF-M]` | Medium confidence inference | Estimated with ±15% margin |
| `[INF-B]` | Low confidence inference | Estimated with ±30% margin or higher |
| `[N/A]` | Not available | API does not provide this data |

---

## Installation

```bash
npx skills add JoseArroyave/agent-skills --skill football-analysis-engine
```

---

## Usage (Agent)

The skill activates automatically when keywords are detected such as:

```
match, Champions, League, form, current form, team statistics,
H2H, head-to-head, background, over/under, both teams score, BTTS,
corners, cards, clean sheet, streak, trend, quantitative analysis,
prediction, home/away performance, scorers, assists, xG inferred,
recent form, rolling window, correlation, outlier, pattern analysis
```

---

## Input

### Activation by Query

The skill responds to queries like:

- "analyze tomorrow's match"
- "how is Real Madrid coming in"
- "Barcelona vs Bayern prediction"
- "Liverpool's current home form"
- "H2H between these teams"

---

## Output Format

The analysis follows this structure:

1. Global Form — Home Team
2. Global Form — Away Team
3. Head-to-Head
4. Quantitative Prediction
5. Statistical Insights
6. Recommendations
7. Quick Guide — Data Reuse

---

## Skill Principles

1. **Global before specific**: Always cross league + cup + Europe
2. **Data, not opinion**: Every claim backed by data
3. **Explicit confidence**: Every prediction includes its confidence level
4. **Rate limiting respected**: Prioritize calls if approaching the limit
5. **Outliers documented**: Atypical results are excluded/downgraded/noted
6. **Cautious correlations**: Only with N>=10
7. **Inferred metrics explicit**: Tag as [INF-M] or [INF-B]
8. **Descriptive prediction**: "team scores 2.1 goals on average" — NOT "bet on Over"
9. **Always structured output**: Identical format for comparability
10. **Fast vs deep mode**: User chooses, don't force

---

## Analysis Storage

Analyses are saved to:

```
./claude/skills/football-analysis-engine/Análisis deportivos/
```

Folder structure by competition:

```
Champions League 25-26/
LaLiga 25-26/
Premier League 25-26/
...
```

File naming:

```
HOMETEAM_AWAYTEAM_DD_MM_YYYY(ROUND_X).txt
```

Example:

```
RealMadrid_Barcelona_15_05_2026(ROUND_34).txt
Bayern_Liverpool_01_04_2026(QUARTERS_2).txt
```
