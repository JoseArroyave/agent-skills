# notion-movies

An intelligent movie knowledge skill for AI agents.

This skill transforms a Notion database into a semantic, self-enriching movie system with:

- automatic enrichment (TMDB)
- semantic search (embeddings)
- explainable recommendations
- duplicate detection (semantic + fuzzy)
- vector indexing (Qdrant)

The agent interacts with a unified system that handles ingestion, enrichment, and retrieval seamlessly.

---

## System Requirements

This skill uses APIs and local services. Ensure the following are available:

### Required Services

- **Notion API**
- **TMDB API**

### Optional (for advanced features)

- **Ollama** (embeddings generation)
- **Qdrant** (vector database)

---

## Verify Installation

### Check Ollama

```bash
curl http://localhost:11434
````

### Check Qdrant

```bash
curl http://localhost:6333
```

If both respond, services are running correctly.

---

## Architecture

User
→ Agent
→ notion-movies skill
  ├── Notion (database storage)
  ├── TMDB (movie metadata enrichment)
  ├── Ollama (embeddings generation)
  └── Qdrant (semantic search index)
  ↓
Agent receives structured enriched data
↓
User

---

## Core Behavior

* Movies are added with minimal input (title only)
* TMDB enriches all metadata automatically
* Duplicate detection prevents redundant entries
* Embeddings enable semantic understanding
* Results are explainable (not just ranked)
* Notion becomes a dynamic knowledge system

---

## What This Skill Actually Does

This is not just a CRUD tool.

It converts:

```
Notion = static movie list
```

Into:

```
Notion = intelligent movie knowledge system
```

---

## Capabilities

### 🎬 Smart Movie Ingestion

```txt
"add Interstellar"
```

→ Creates page
→ Enriches with TMDB data
→ Adds poster, plot, director, genres
→ Adds actors, runtime, year
→ Generates embedding

---

### 🧬 Duplicate Detection

Prevents:

* Interstellar
* Interstellar (2014)
* Interestellar ❌

Uses:

* fuzzy matching (Levenshtein)
* normalized titles (removes year)
* semantic similarity (embeddings)

---

### 🔎 Semantic Search (Explainable)

```txt
"movies about time travel"
"romantic movies in Europe"
"movies like Nolan"
```

Returns:

* semantically relevant results
* similarity score
* explanation of why it matches

Example:

```json
{
  "title": "Interstellar",
  "score": 0.92,
  "explanation": "Similar because: genre similarity, plot similarity"
}
```

---

### 🤖 Recommendations

```txt
"recommend something like Fight Club"
```

→ Finds semantically similar movies using embeddings

---

### 🧠 Knowledge System

Transforms your Notion DB into:

* searchable
* self-enriching
* explainable
* agent-usable memory

---

## 🧠 Embedding Strategy

Embeddings are built using enriched semantic content:

* Title
* Genres
* Director
* Plot
* Inferred themes

Example:

```txt
Title: Interstellar
Genres: Science Fiction, Drama
Director: Christopher Nolan
Plot: A team travels through a wormhole in space...

Themes: space, time, futuristic
```

### Optimization

* Important fields are repeated (weighting)
* Themes inferred from plot
* Improves semantic recall and ranking quality

---

## 🔐 Edge Case Handling

### ❌ Movie not found

```json
{
  "error": "Movie not found in TMDB"
}
```

---

### ⚠️ Ambiguous matches

```json
{
  "error": "Multiple matches found",
  "options": [
    { "title": "Dune", "year": "2021" },
    { "title": "Dune", "year": "1984" }
  ]
}
```

---

### 🧠 Embedding fallback

* Returns zero vector if embedding fails
* Prevents crashes
* Keeps pipeline running

---

## Data Enrichment Pipeline

1. Search movie in TMDB
2. Fetch:

   * poster
   * plot
   * genres
   * director (credits)
   * actors
   * runtime
   * year
3. Update Notion properties
4. Add Notion blocks
5. Generate embedding
6. Store vector in Qdrant

---

## Notion Schema

### Required

| Property    | Type         |
| ----------- | ------------ |
| Nombre      | title        |
| Director/es | rich_text    |
| Género      | multi_select |
| Portada     | files        |
| Rating      | select       |
| Estado      | status       |

---

### Recommended (Extended)

| Property | Type      | Description  |
| -------- | --------- | ------------ |
| Año      | number    | Release year |
| Actores  | rich_text | Main cast    |
| Duración | number    | Runtime      |

---

## When To Use

Use this skill when:

* Managing a personal movie database
* Building recommendation systems
* Enriching content automatically
* Avoiding duplicates
* Enabling semantic search over structured data

---

## When NOT To Use

Do not use this skill when:

* You only need simple CRUD
* No enrichment is required
* No semantic search is needed
* External APIs are unavailable

---

## Installation

```bash
npx skills add JoseArroyave/agent-skills --skill notion-movies
```

---

## Usage (Agent)

### Add Movie

```json
{
  "tool": "notion-movies.addMovie",
  "input": {
    "title": "Interstellar",
    "databaseQuery": "Movies"
  }
}
```

---

### Enrich Movie

```json
{
  "tool": "notion-movies.enrichMovie",
  "input": {
    "title": "Interstellar",
    "databaseQuery": "Movies"
  }
}
```

---

### Search Movies

```json
{
  "tool": "notion-movies.searchMovies",
  "input": {
    "query": "movies about space exploration"
  }
}
```

---

### Detect Duplicate

```json
{
  "tool": "notion-movies.detectDuplicate",
  "input": {
    "title": "Interstellar",
    "databaseQuery": "Movies"
  }
}
```

---

## Input

### Required

* `title` (for add/enrich)
* `query` (for search)
* `databaseQuery` (Notion DB name)

---

## Environment Variables

### Required

* `NOTION_API_KEY`
* `TMDB_API_KEY`

### Optional

* `QDRANT_URL` (default: [http://localhost:6333](http://localhost:6333))
* `OLLAMA_URL` (default: [http://localhost:11434](http://localhost:11434))

---

## Output Behavior

### addMovie

```json
{
  "success": true
}
```

or:

```json
{
  "duplicate": true,
  "message": "Movie already exists, enriching instead"
}
```

---

### enrichMovie

```json
{
  "success": true
}
```

or (edge cases):

```json
{
  "error": "Multiple matches found",
  "options": [...]
}
```

---

### searchMovies

```json
[
  {
    "title": "Interstellar",
    "score": 0.94,
    "explanation": "Similar because: plot similarity"
  }
]
```

---

### detectDuplicate

```json
{
  "duplicate": true,
  "match": "Interstellar",
  "score": 0.97
}
```

---

## Design Goals

* Zero manual data entry
* Semantic understanding over keyword matching
* Explainable recommendations
* Deterministic duplicate prevention
* Agent-first design
* Extensible architecture
* Minimal user friction