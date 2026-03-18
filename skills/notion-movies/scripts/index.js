import levenshtein from 'fast-levenshtein';
import { Client } from '@notionhq/client';
import dotenv from 'dotenv';
import https from 'https';

dotenv.config({ path: '/home/jose/.openclaw/.env' });

/* =========================
   ⚙️ CONFIG
========================= */

const notion = new Client({ auth: process.env.NOTION_API_KEY });

const EMBEDDING_MODEL = process.env.EMBEDDING_MODEL || 'nomic-embed-text:v1.5';
const NOTION_MOVIES_MODEL = process.env.NOTION_MOVIES_MODEL || 'llama3.2:3b';
const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const QDRANT_URL = process.env.QDRANT_URL || 'http://localhost:6333';
const TMDB_API_KEY = process.env.TMDB_API_KEY;
const DATABASE_NAME = 'Movies';

const COLLECTION = 'movies';
const VECTOR_SIZE = 768;

/* =========================
   🔎 DATABASE
========================= */

async function findDatabase() {
  const res = await notion.search({
    query: DATABASE_NAME,
    filter: { value: "data_source", property: "object" }
  });

  if (!res.results.length) throw new Error(`Database not found: ${DATABASE_NAME}`);
  return res.results[0].id;
}

async function getAllPages(databaseId) {
  let pages = [];
  let cursor;
  let hasMore = true;

  while (hasMore) {
    const res = await notion.dataSources.query({
      data_source_id: databaseId,
      start_cursor: cursor
    });

    pages.push(...res.results);
    hasMore = res.has_more;
    cursor = res.next_cursor;
  }

  return pages;
}

/* =========================
   🎬 TMDB
========================= */

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject);
  });
}

async function getMovieData(title) {
  const search = await fetchJson(
    `https://api.themoviedb.org/3/search/movie?api_key=${TMDB_API_KEY}&query=${encodeURIComponent(title)}`
  );

  if (!search.results?.length) {
    return { error: 'NOT_FOUND' };
  }

  const scored = search.results.map(movie => ({
    score: scoreMovie(title, movie),
    movie
  }));

  // ordenar por score descendente
  scored.sort((a, b) => b.score - a.score);

  const best = scored[0];

  // 🧠 threshold inteligente
  if (best.score < 0.75) {
    return {
      error: 'AMBIGUOUS',
      options: search.results.slice(0, 5).map(m => ({
        title: m.title,
        year: m.release_date?.split('-')[0]
      }))
    };
  }

  const movie = best.movie;

  const details = await fetchJson(
    `https://api.themoviedb.org/3/movie/${movie.id}?api_key=${TMDB_API_KEY}`
  );

  const credits = await fetchJson(
    `https://api.themoviedb.org/3/movie/${movie.id}/credits?api_key=${TMDB_API_KEY}`
  );

  const director = credits.crew.find(c => c.job === 'Director')?.name;

  return {
    title: movie.title,
    plot: movie.overview,
    poster: movie.poster_path
      ? `https://image.tmdb.org/t/p/w500${movie.poster_path}`
      : null,
    genres: details.genres?.map(g => g.name) || [],
    director,
    year: movie.release_date?.split('-')[0],
    runtime: details.runtime,
    language: details.original_language,
    actors: credits.cast.slice(0, 5).map(a => a.name)
  };
}

/* =========================
   📄 HELPERS
========================= */

function normalizeTitle(t) {
  return t.toLowerCase().replace(/\(\d{4}\)/, '').trim();
}

function isDuplicate(a, b) {
  return isFuzzy(normalizeTitle(a), normalizeTitle(b));
}

function getTitle(page) {
  return page.properties['Nombre']?.title?.[0]?.text?.content;
}

function getDirector(page) {
  return page.properties['Director/es']?.rich_text?.[0]?.text?.content || '';
}

function getGenres(page) {
  return page.properties['Género']?.multi_select?.map(g => g.name) || [];
}

function getThemes(page) {
  return page.properties['Themes']?.multi_select?.map(t => t.name) || [];
}

function getActors(page) {
  return page.properties['Actores']?.multi_select?.map(a => a.name) || [];
}

function hasPortada(page) {
  return (page.properties.Portada?.files || []).length > 0;
}

function hasDirector(page) {
  return getDirector(page) !== '';
}

function hasGenres(page) {
  return getGenres(page).length > 0;
}

function hasActors(page) {
  return getActors(page).length > 0;
}

function hasEmoji(page) {
  return page.icon?.type === 'emoji';
}

function rerank(results, baseMovie) {
  return results.map(r => {

    let bonus = 0;

    // 🎭 themes overlap
    const themesMatch = r.themes?.some(t => baseMovie.themes?.includes(t));
    if (themesMatch) bonus += 0.1;

    // 🎬 mismo género
    const genreMatch = r.genres?.some(g => baseMovie.genres?.includes(g));
    if (genreMatch) bonus += 0.05;

    return {
      ...r,
      final_score: r.score + bonus
    };
  })
    .sort((a, b) => b.final_score - a.final_score);
}

async function findMovieInDB(title) {
  const dbId = await findDatabase();
  const pages = await getAllPages(dbId);

  return pages.find(p =>
    isDuplicate(getTitle(p), title)
  );
}

function cleanTitle(title) {
  return title
    .replace(/^\(/, '')        // (500 → 500
    .replace(/\)/g, '')        // quitar )
    .replace(/\(\d{4}\)/, '')  // (2010)
    .trim();
}

async function existsInQdrant(id) {
  const res = await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points/${id}`);
  const data = await res.json();
  return !!data.result;
}

async function extractPlotFromPage(page) {
  const blocks = await notion.blocks.children.list({
    block_id: page.id
  });
  const quoteBlock = blocks.results.find(b => b.type === 'quote');
  return quoteBlock?.quote?.rich_text?.[0]?.text?.content || '';
}

function scoreMovie(query, movie) {
  const normalizedQuery = query.toLowerCase();
  const normalizedTitle = movie.title.toLowerCase();

  // 1. Similaridad (0 → mejor)
  const distance = levenshtein.get(normalizedQuery, normalizedTitle);

  // Normalizamos (más bajo = mejor → invertimos)
  const similarityScore = 1 - (distance / Math.max(normalizedQuery.length, normalizedTitle.length));

  // 2. Popularidad (0 → 1)
  const popularityScore = Math.min(movie.popularity / 100, 1);

  // 3. Bonus si el título contiene exactamente el query
  const exactMatchBonus = normalizedTitle.includes(normalizedQuery) ? 0.2 : 0;

  // 🔥 Score final ponderado
  return (
    similarityScore * 0.7 +
    popularityScore * 0.2 +
    exactMatchBonus
  );
}

function explainScore(query, payload, score) {
  const reasons = [];
  const q = query.toLowerCase();

  const tokens = q.split(/\s+/);

  if (payload.genres?.some(g =>
    tokens.some(t => g.toLowerCase().includes(t))
  )) {
    reasons.push('genre similarity');
  }

  if (payload.director &&
    tokens.some(t => payload.director.toLowerCase().includes(t))) {
    reasons.push('director match');
  }

  if (payload.plot &&
    tokens.some(t => payload.plot.toLowerCase().includes(t))) {
    reasons.push('plot similarity');
  }

  if (payload.themes?.some(t =>
    tokens.some(token => t.includes(token))
  )) {
    reasons.push('theme similarity');
  }

  return {
    score: Number(score.toFixed(3)),
    explanation: reasons.length
      ? `Similar because: ${reasons.join(', ')}`
      : 'General semantic similarity'
  };
}

function buildPayload({ title, genres, director, plot, page, themes }) {
  return {
    text: `${title}. ${genres.join(', ')}. ${director}. ${plot}`,
    genre_text: genres.join(', '),
    title: cleanTitle(title),
    notionPageId: page.id,
    has_plot: !!plot,
    director,
    genres,
    themes,
    plot
  };
}

function safeParseThemes(text) {
  try {
    const json = JSON.parse(text);
    return Array.isArray(json) ? json : [];
  } catch {
    const match = text.match(/\[(.*?)\]/);
    if (!match) return [];

    return match[1]
      .split(',')
      .map(t => t.replace(/["']/g, '').trim())
      .filter(Boolean);
  }
}

async function extractThemesLLM(plot) {
  try {
    const res = await fetch(`${OLLAMA_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: NOTION_MOVIES_MODEL,
        prompt: `
          Extract 3 to 5 high-level themes from this movie plot.

          Rules:
          - Return ONLY a JSON array
          - No explanation
          - Use short phrases
          - Lowercase

          Plot:
          ${plot}`,
        stream: false
      })
    });

    const json = await res.json();

    // 👇 respuesta viene como string
    const text = json.response?.trim();

    // intentar parsear JSON
    const themes = safeParseThemes(text);

    return Array.isArray(themes) ? themes : [];

  } catch (e) {
    console.error('LLM theme extraction failed:', e);
    return [];
  }
}

/* =========================
🖼️ ENRICH FUNCTIONS
========================= */

async function ensureCollection() {
  const res = await fetch(`${QDRANT_URL}/collections/${COLLECTION}`);
  const data = await res.json();

  if (data.status.error && data.status.error === "Not found: Collection `movies` doesn't exist!") {
    console.log('⚠️ Creating collection...');

    await fetch(`${QDRANT_URL}/collections/${COLLECTION}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vectors: {
          size: VECTOR_SIZE,
          distance: 'Cosine'
        }
      })
    });
  }
}

async function ensureYear(page, year) {
  if (!year) return;

  await notion.pages.update({
    page_id: page.id,
    properties: {
      'Año': { number: parseInt(year) }
    }
  });
}

async function ensureActors(page, actors) {
  if (hasActors(page) || !actors.length) return;

  await notion.pages.update({
    page_id: page.id,
    properties: {
      'Actores': {
        multi_select: actors.map(a => ({ name: a }))
      }
    }
  });
}

async function ensureRuntime(page, runtime) {
  if (!runtime) return;

  await notion.pages.update({
    page_id: page.id,
    properties: {
      'Duración': { number: runtime }
    }
  });
}

async function ensureEmoji(page) {
  if (hasEmoji(page)) return;

  await notion.pages.update({
    page_id: page.id,
    icon: { type: 'emoji', emoji: '🎬' }
  });
}

async function ensureDirector(page, director) {
  if (hasDirector(page) || !director) return;

  await notion.pages.update({
    page_id: page.id,
    properties: {
      'Director/es': {
        rich_text: [{ text: { content: director } }]
      }
    }
  });
}

async function ensureGenres(page, genres) {
  if (hasGenres(page) || !genres.length) return;

  await notion.pages.update({
    page_id: page.id,
    properties: {
      'Género': {
        multi_select: genres.map(g => ({ name: g }))
      }
    }
  });
}

async function ensurePortada(page, title, url) {
  if (hasPortada(page) || !url) return;

  await notion.pages.update({
    page_id: page.id,
    properties: {
      Portada: {
        files: [
          {
            type: 'external',
            external: { url },
            name: title
          }
        ]
      }
    }
  });
}

async function ensureCover(page, url) {
  if (!url) return;

  await notion.pages.update({
    page_id: page.id,
    cover: {
      type: 'external',
      external: { url }
    }
  });
}

async function ensurePlot(page, plot) {
  if (!plot) return;

  await notion.blocks.children.append({
    block_id: page.id,
    children: [
      {
        object: 'block',
        type: 'callout',
        callout: {
          rich_text: [{ annotations: { italic: true }, text: { content: 'Plot' }, type: 'text' }],
          icon: { type: 'emoji', emoji: '💡' },
          color: 'gray_background'
        }
      },
      {
        object: 'block',
        type: 'quote',
        quote: {
          rich_text: [{ type: 'text', text: { content: plot } }]
        }
      }
    ]
  });
}

async function ensureRating(page, rating) {
  const name = rating || 'Sin calificar';

  await notion.pages.update({
    page_id: page.id,
    properties: {
      Rating: { select: { name } }
    }
  });
}

/* =========================
   🧠 EMBEDDINGS
========================= */

async function findMovieInQdrantByTitle(title) {
  const res = await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points/scroll`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      limit: 1,
      with_payload: true,
      with_vector: true, // 🔥 IMPORTANTE
      filter: {
        must: [
          {
            key: 'title',
            match: { value: title }
          }
        ]
      }
    })
  });

  const data = await res.json();

  return data.result?.points?.[0] || null;
}

function buildText(movie) {
  return `
    Movie: ${movie.title}

    This is a ${movie.genres?.join(', ')} film
    directed by ${movie.director}.

    Plot:
    ${movie.plot}

    Themes:
    ${movie.themes?.join(', ')}

    This movie explores:
    ${movie.themes?.join(', ')}

    Keywords:
    ${movie.genres?.join(', ')}, ${movie.director}
      `.trim();
}

async function embed(text) {
  try {
    const res = await fetch(`${OLLAMA_URL}/api/embeddings`, {
      method: 'POST',
      body: JSON.stringify({
        model: EMBEDDING_MODEL,
        prompt: text
      })
    });

    const json = await res.json();
    return json.embedding;

  } catch (e) {
    console.error('Embedding failed:', e);
    return new Array(VECTOR_SIZE).fill(0); // fallback seguro
  }
}
/* =========================
   🗄️ QDRANT
========================= */

async function upsertVector(movie) {
  await ensureCollection();

  const vector = await embed(buildText(movie));

  await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      points: [
        {
          id: movie.notionPageId,
          payload: movie,
          vector
        }
      ]
    })
  });
}

/* =========================
   🧬 DUPLICATE
========================= */

function isFuzzy(a, b) {
  return levenshtein.get(a.toLowerCase(), b.toLowerCase()) <= 2;
}

/* =========================
   🚀 MAIN ACTIONS
========================= */

export async function recommendMovies({ title }) {

  // 1. buscar en Notion
  let page = await findMovieInDB(title);

  // 2. si no existe → crear + enriquecer
  if (!page) {
    console.log(`Movie not found. Adding + enriching: ${title}`);

    await addMovie({ title });
    await enrichMovie({ title });

    page = await findMovieInDB(title);
  }

  const titleFromPage = getTitle(page);

  // 3. traer desde Qdrant (con vector)
  const point = await findMovieInQdrantByTitle(titleFromPage);

  if (!point) {
    throw new Error('Movie not indexed in Qdrant');
  }

  // 🔥 usar el vector existente
  const vector = point.vector;

  // 4. búsqueda semántica REAL
  const res = await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      with_payload: true,
      limit: 10,
      vector
    })
  });

  const data = await res.json();

  const results = data.result
    .filter(r => r.id !== point.id)
    .map(r => ({
      ...r.payload,
      score: r.score
    }));

  return rerank(results, point.payload);
}

export async function indexAllMovies() {
  console.log('🚀 Starting full indexing...\n');

  const dbId = await findDatabase();
  const pages = await getAllPages(dbId);

  console.log(`📄 Found ${pages.length} movies\n`);

  let indexed = 0;
  let skipped = 0;

  for (const page of pages) {
    try {

      const title = getTitle(page);

      if (!title) {
        skipped++;
        continue;
      }

      if (await existsInQdrant(page.id)) {
        console.log(`⏭️ Already indexed: ${title}`);
        continue;
      }

      console.log(`🎬 Processing: ${title}`);

      const plot = await extractPlotFromPage(page) || '';
      const existingThemes = getThemes(page);
      const director = getDirector(page);
      const genres = getGenres(page);

      const themes = (!existingThemes.length) ? await extractThemesLLM(plot) : existingThemes;

      const payload = buildPayload({ director, genres, title, plot, page, themes });
      await upsertVector(payload);

      indexed++;
      console.log(`✅ Indexed: ${title}\n`);

    } catch (e) {
      console.log(`❌ Error with ${getTitle(page)}: ${e.message}\n`);
      skipped++;
    }
  }

  console.log('\n🎉 DONE');
  console.log(`✅ Indexed: ${indexed}`);
  console.log(`⚠️ Skipped: ${skipped}`);
}

export async function addMovie({ title }) {
  const dbId = await findDatabase();
  const pages = await getAllPages(dbId);

  const existing = pages.find(p =>
    isDuplicate(getTitle(p), title)
  );

  if (existing) {
    return {
      duplicate: true,
      message: 'Movie already exists, enriching instead'
    };
  }

  await notion.pages.create({
    parent: { data_source_id: dbId },
    properties: {
      Nombre: { title: [{ text: { content: title } }] }
    }
  });

  return { success: true };
}

export async function enrichMovie({ title }) {

  const dbId = await findDatabase();
  const pages = await getAllPages(dbId);

  const page = pages.find(p => getTitle(p) === title);
  if (!page) throw new Error('Movie not found');

  const data = await getMovieData(title);
  if (!data) return { skipped: true };

  if (data.error === 'NOT_FOUND') {
    return {
      error: 'Movie not found in TMDB'
    };
  }

  if (data.error === 'AMBIGUOUS') {
    return {
      error: 'Multiple matches found',
      options: data.options
    };
  }

  const { director, runtime, rating, genres, actors, poster, year, plot } = data;

  await ensureEmoji(page);
  await ensureDirector(page, director);
  await ensureGenres(page, genres);
  await ensureYear(page, year);
  await ensureActors(page, actors);
  await ensureRuntime(page, runtime);
  await ensurePortada(page, title, poster);
  await ensureCover(page, poster);
  await ensurePlot(page, plot);
  await ensureRating(page, rating);

  const existingThemes = getThemes(page);
  const themes = (!existingThemes.length) ? await extractThemesLLM(plot) : existingThemes;

  const payload = buildPayload({ director, themes, genres, title, plot, page });
  await upsertVector(payload);

  return { success: true };
}

export async function searchMovies({ query }) {

  // 🧠 1. enriquecer query (muy importante)
  const fullQuery = `
    User is searching for movies with the following intent:
    
    ${query}
    
    Focus on:
    - themes
    - emotional tone
    - relationships
    - character dynamics
    
    Return semantically similar movies.
    `;

  const vector = await embed(fullQuery);

  // 🔎 2. traer más candidatos (para reranking)
  const res = await fetch(`${QDRANT_URL}/collections/${COLLECTION}/points/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vector,
      limit: 15, // 🔥 antes 5 → ahora más para rerank
      with_payload: true
    })
  });

  const data = await res.json();

  if (!data.result) throw new Error(data.status?.error || 'Qdrant search failed');

  const tokens = query.toLowerCase().split(/\s+/);

  // 🧠 3. reranking híbrido
  const reranked = data.result.map(r => {

    const payload = r.payload;
    let bonus = 0;

    // 🎭 themes match (🔥 lo más importante)
    const themesMatch = payload.themes?.some(t => tokens.some(token => t.toLowerCase().includes(token)));
    if (themesMatch) bonus += 0.15;

    // 🎬 genres match
    const bonusMatch = payload.genres?.some(g => tokens.some(token => g.toLowerCase().includes(token)));
    if (bonusMatch) bonus += 0.07;

    // 🧠 plot match (light boost)
    const plotMatch = payload.plot && tokens.some(t => payload.plot.toLowerCase().includes(t));
    if (plotMatch) bonus += 0.05;

    return {
      ...payload,
      score: r.score,
      final_score: r.score + bonus,
      ...explainScore(query, payload, r.score)
    };
  });

  // 🏆 4. ordenar por score final
  return reranked
    .sort((a, b) => b.final_score - a.final_score)
    .slice(0, 5);
}