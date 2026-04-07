# AI Agent Skills

A personal collection of skills for AI agents. Feel free to use.

## Install the repository

`npx skills add JoseArroyave/agent-skills`

## Install a specific skill

`npx skills add JoseArroyave/agent-skills --skill <skill-name>`

## Available skills

- [**gemini-tavily-search**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/gemini-tavily-search): An intelligent web search orchestration skill. It first consults Gemini to determine whether a web search is required, then uses [Google Search Grounding](https://ai.google.dev/gemini-api/docs/google-search?hl=es-419) through supported [Gemini models](https://ai.google.dev/gemini-api/docs/google-search?hl=es-419#supported_models). If grounding fails, it automatically falls back to [Tavily](https://www.tavily.com/) using a configured API key. Finally, it normalizes the response into a consistent JSON schema and returns it to the agent.

- [**notion-movies**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/notion-movies): A Notion-based movie management and semantic search skill. It allows agents to add and enrich movies using TMDB (poster, plot, director, genres), prevent duplicates using semantic + fuzzy matching, and perform embedding-based search using Ollama and Qdrant.

- [**football-analysis-engine**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/football-analysis-engine): Quantitative football analysis engine based on RapidAPI Hub - Free API Live Football Data. Provides descriptive analysis, quantitative predictions with confidence levels, pattern and correlation detection, rolling window form evaluation, and statistical recommendations for matches and players.
