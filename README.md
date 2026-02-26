# AI Agent Skills

A personal collection of skills for AI agents. Feel free to use.

## Install the repository

`npx skills add JoseArroyave/agent-skills`

## Install a specific skill

`npx skills add JoseArroyave/agent-skills --skill <skill-name>`

## Available skills

- [**gemini-tavily-search**](https://github.com/JoseArroyave/agent-skills/tree/main/skills/gemini-tavily-search): An intelligent web search orchestration skill. It first consults Gemini to determine whether a web search is required, then uses [Google Search Grounding](https://ai.google.dev/gemini-api/docs/google-search?hl=es-419) through supported [Gemini models](https://ai.google.dev/gemini-api/docs/google-search?hl=es-419#supported_models). If grounding fails, it automatically falls back to [Tavily](https://www.tavily.com/) using a configured API key. Finally, it normalizes the response into a consistent JSON schema and returns it to the agent.
