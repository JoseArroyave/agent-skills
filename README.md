# AI Agent Skills

A personal collection of skills for AI agents. Feel free to use.

## Install the repository

`npx skills add JoseArroyave/agent-skills`

## Install a specific skill

`npx skills add JoseArroyave/agent-skills --skill <skill-name>`

## Available skills

- [**gemini-tavily-search**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/gemini-tavily-search): An intelligent web search orchestration skill. It first consults Gemini to determine whether a web search is required, then uses [Google Search Grounding](https://ai.google.dev/gemini-api/docs/google-search?hl=es-419) through supported [Gemini models](https://ai.google.dev/gemini-api/docs/google-search?hl=es-419#supported_models). If grounding fails, it automatically falls back to [Tavily](https://www.tavily.com/) using a configured API key. Finally, it normalizes the response into a consistent JSON schema and returns it to the agent.

- [**notion-movies**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/notion-movies): A Notion-based movie management and semantic search skill. It allows agents to add and enrich movies using TMDB (poster, plot, director, genres), prevent duplicates using semantic + fuzzy matching, and perform embedding-based search using Ollama and Qdrant.

- [**football-betting-analysis**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/football-betting-analysis): Pre-match football betting analysis in 8 layers. Uses `teams.csv` + FlashScore MCP (`Get_Team_Fixtures` → `Get_Team_Results` fallback) for match discovery, then executes `build_match_context.py` which internally calls all FlashScore endpoints and returns a single normalized JSON (`final_context`). The model only reads that JSON — it does not call MCP endpoints directly for match data. Produces a structured report with probabilistic language. Only analyzes `notstarted` events. No invented data — missing fields are marked `[N/A]`. Probabilities in Layer 7 come from odds only; indicators modulate confidence but never generate percentages.
