#!/usr/bin/env bash
# Gemini -> (any error) -> Tavily fallback
# Usage:
#   ./scripts/gemini_tavily_search.sh '<json>'
# Example:
#   ./scripts/gemini_tavily_search.sh '{"query":"Who won the euro 2024?","max_results":5}'

set -euo pipefail

JSON_INPUT="${1:-}"
if [[ -z "$JSON_INPUT" ]]; then
  echo "Usage: ./scripts/gemini_tavily_search.sh '<json>'" >&2
  exit 1
fi

# Dependencies
command -v curl >/dev/null 2>&1 || { echo "Error: curl not found" >&2; exit 1; }
command -v jq   >/dev/null 2>&1 || { echo "Error: jq not found" >&2; exit 1; }

# Validate JSON
if ! echo "$JSON_INPUT" | jq empty >/dev/null 2>&1; then
  echo "Error: Invalid JSON input" >&2
  exit 1
fi

# Require query field
QUERY="$(echo "$JSON_INPUT" | jq -r '.query // empty')"
if [[ -z "$QUERY" || "$QUERY" == "null" ]]; then
  echo "Error: 'query' field is required" >&2
  exit 1
fi

# ---------- Config ----------
: "${GEMINI_API_KEY:=}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash-lite}"
GEMINI_URL="https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent"

# Keep it tight (you can tweak later)
GEMINI_CLASSIFY_TIMEOUT_SECONDS=8
GEMINI_TIMEOUT_SECONDS=20

# Optional shaping
MAX_RESULTS="$(echo "$JSON_INPUT" | jq -r '.max_results // empty')"
TIME_RANGE="$(echo "$JSON_INPUT" | jq -r '.time_range // empty')"

# ---------- Helpers ----------
stderr() { printf "%s\n" "$*" >&2; }

needs_web_by_heuristic() {
  local q="$1"
  local q_lower
  q_lower="$(echo "$q" | tr '[:upper:]' '[:lower:]')"

  # Señales típicas de tiempo real
  if echo "$q_lower" | grep -E -q \
    "(hoy|ahora|actual|último|ultimos|últimos|reciente|precio|cotización|cuánto quedó|marcador|noticia|news|today|current|latest|price|score|stock|update|breaking)"; then
    return 0  # YES
  fi

  return 1  # NO
}

# Decide si la pregunta requiere info actual (web) usando una mini-llamada a Gemini SIN tools.
# Devuelve:
#   0 => YES (usar google_search)
#   1 => NO  (no usar google_search)
should_use_web_via_gemini() {
  local q="$1"
  local timeout="${GEMINI_CLASSIFY_TIMEOUT_SECONDS:-8}"

  # Prompt corto y bien estricto
  local classify_body
  classify_body="$(jq -n --arg q "$q" '{
    contents: [{
      parts: [{
        text: "Answer ONLY with YES or NO.\nQuestion: \($q)\nDoes this question require up-to-date web information (news, current events, prices, recently changed facts) to answer correctly?"
      }]
    }]
  }')"

  # Llamada ligera (sin tools)
  local resp_with_code http body curl_code
  set +e
  resp_with_code="$(
    curl -sS --connect-timeout 5 --max-time "$timeout" \
      -H "x-goog-api-key: $GEMINI_API_KEY" \
      -H "Content-Type: application/json" \
      -X POST \
      -d "$classify_body" \
      -w "\n__HTTP_STATUS__:%{http_code}\n" \
      "$GEMINI_URL"
  )"
  curl_code=$?
  set -e

  # Si falla la clasificación, por ahorro asumimos NO (no web)
  if [[ $curl_code -ne 0 || -z "$resp_with_code" ]]; then
    if needs_web_by_heuristic "$q"; then
      return 0
    fi
    return 1
  fi

  http="$(echo "$resp_with_code" | sed -n 's/^__HTTP_STATUS__:\([0-9]\+\)$/\1/p' | tail -1)"
  body="$(echo "$resp_with_code" | sed '/^__HTTP_STATUS__:/d')"

  if [[ -z "$http" || "$http" -lt 200 || "$http" -ge 300 ]]; then
    if needs_web_by_heuristic "$q"; then
      return 0
    fi
    return 1
  fi

  # Extrae texto del candidato
  local ans
  ans="$(echo "$body" | jq -r '
    (.candidates // [])
    | map(.content.parts // [])
    | flatten
    | map(.text? // empty)
    | map(select(. != ""))
    | join(" ")
  ' 2>/dev/null || true)"

  # Normaliza
  ans="$(echo "$ans" | tr -d '\r' | tr '\n' ' ' | tr '[:lower:]' '[:upper:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

  if echo "$ans" | grep -q "YES"; then
    return 0
  fi

  # Si respondió NO explícitamente, respeta NO
  if echo "$ans" | grep -q "NO"; then
    return 1
  fi

  # Si no fue claro, aplica heurística
  if needs_web_by_heuristic "$q"; then
    return 0
  fi

  return 1
}

build_gemini_body() {
  local q="$1"

  # Por defecto: NO tools
  if should_use_web_via_gemini "$q"; then
    jq -n --arg q "$q" '{
      contents: [{ parts: [{ text: $q }] }],
      tools: [{ google_search: {} }]
    }'
  else
    jq -n --arg q "$q" '{
      contents: [{ parts: [{ text: $q }] }]
    }'
  fi
}

normalize_tavily_to_unified() {
  jq -c '{
    results: (.results // [] | map({title, url, snippet: (.content // null)})),
    provider: "tavily",
    used_web: true,
    fallback: true,
    answer: null
  }'
}

tavily_fallback() {
  set +e
  local out
  out="$(bash "$(dirname "$0")/tavily_search.sh" "$JSON_INPUT" 2>/dev/null)"
  local code=$?
  set -e

  if [[ $code -eq 0 && -n "$out" ]] && echo "$out" | jq empty >/dev/null 2>&1; then
    echo "$out" | normalize_tavily_to_unified
    return 0
  fi

  jq -n '{
    provider: "tavily",
    answer: null,
    results: [],
    fallback: true,
    error: "tavily_failed"
  }'
  return 0
}

normalize_gemini_to_tavilyish_json() {
  jq -c '
  # 1) Texto final del modelo
  def answer_text:
    (.candidates // [])
    | map(.content.parts // [])
    | flatten
    | map(.text? // empty)
    | map(select(. != ""))
    | join("\n");

  # 2) Grounding metadata del primer candidato (normalmente viene ahí)
  def gm: (.candidates[0].grounding_metadata // {});

  # 3) Chunks web con índice (para poder unir con supports por indices)
  def chunks:
    (gm.grounding_chunks // [])
    | to_entries
    | map({
        idx: .key,
        title: (.value.web.title // null),
        url: (.value.web.uri // null)
      })
    | map(select(.url != null));

  # 4) Supports: texto + indices de chunks a los que soporta
  def supports:
    (gm.grounding_supports // [])
    | map({
        indices: (.grounding_chunk_indices // []),
        text: (.segment.text // empty)
      })
    | map(select(.text != "" and (.indices|length > 0)));

  # 5) Para cada chunk, juntar snippets relevantes (supports que lo referencian)
  def results:
    chunks
    | map(. as $c |
        {
          title: $c.title,
          url: $c.url,
          snippet: (
            supports
            | map(select(.indices | index($c.idx) != null) | .text)
            | unique
            | join(" ")
          )
        }
      );

  def used_web:
    ( (gm.web_search_queries // []) | length > 0 )
    or ( (gm.grounding_chunks // []) | length > 0 )
    or ( (gm.search_entry_point.rendered_content? // "") != "" );

  {
  answer: answer_text,
  used_web: used_web,
  provider: "gemini",
  results: results,
  fallback: false
  }'
}

# ---------- Main ----------
# If no Gemini key, jump straight to Tavily
if [[ -z "$GEMINI_API_KEY" ]]; then
  stderr "Gemini key missing; falling back to Tavily."
  tavily_fallback
  exit 0
fi

# Build Gemini request body
# Keep it minimal and stable: text query + google_search tool.
GEMINI_BODY="$(build_gemini_body "$QUERY")"

# Call Gemini with strict timeout, capture both body and HTTP status
set +e
GEMINI_RESP_WITH_CODE="$(
  curl -sS --connect-timeout 5 --max-time "$GEMINI_TIMEOUT_SECONDS" \
    -H "x-goog-api-key: $GEMINI_API_KEY" \
    -H "Content-Type: application/json" \
    -X POST \
    -d "$GEMINI_BODY" \
    -w "\n__HTTP_STATUS__:%{http_code}\n" \
    "$GEMINI_URL"
)"
CURL_CODE=$?
set -e

# Any curl-level error => Tavily
if [[ $CURL_CODE -ne 0 || -z "$GEMINI_RESP_WITH_CODE" ]]; then
  stderr "Gemini curl failed (code=$CURL_CODE). Falling back to Tavily."
  tavily_fallback
  exit 0
fi

HTTP_STATUS="$(echo "$GEMINI_RESP_WITH_CODE" | sed -n 's/^__HTTP_STATUS__:\([0-9]\+\)$/\1/p' | tail -1)"
GEMINI_JSON="$(echo "$GEMINI_RESP_WITH_CODE" | sed '/^__HTTP_STATUS__:/d')"

# Non-2xx => Tavily
if [[ -z "$HTTP_STATUS" || "$HTTP_STATUS" -lt 200 || "$HTTP_STATUS" -ge 300 ]]; then
  stderr "Gemini HTTP status=$HTTP_STATUS. Falling back to Tavily."
  tavily_fallback
  exit 0
fi

# Not JSON => Tavily
if ! echo "$GEMINI_JSON" | jq empty >/dev/null 2>&1; then
  stderr "Gemini returned non-JSON. Falling back to Tavily."
  tavily_fallback
  exit 0
fi

# If Gemini includes an API error field, treat as error => Tavily
HAS_ERROR="$(echo "$GEMINI_JSON" | jq -r 'has("error")')"
if [[ "$HAS_ERROR" == "true" ]]; then
  stderr "Gemini returned error object. Falling back to Tavily."
  tavily_fallback
  exit 0
fi

# Success: normalize and return JSON to agent
echo "$GEMINI_JSON" | normalize_gemini_to_tavilyish_json