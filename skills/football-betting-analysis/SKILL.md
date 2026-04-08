---
name: football-betting-analysis
description: >
  Análisis pre-partido de fútbol en 8 capas. Recibe una consulta en lenguaje
  natural, descubre el partido en la Bzzoiro API, reúne datos y produce un
  informe estructurado con lenguaje probabilístico. Solo usa la Bzzoiro API.
  No inventa datos, no analiza partidos en curso ni finalizados, no suple
  la predicción ML de la API con modelos heurísticos.
---

# Football Betting Analysis

## 1. Overview

Análisis pre-partido de fútbol en 8 capas. Recibe una consulta en lenguaje
natural, descubre el partido en la Bzzoiro API, reúne datos y produce un
informe estructurado con lenguaje probabilístico.

El análisis es una interpretación de la evidencia disponible. No es un pick.
No es una garantía. Siempre usa lenguaje como "podría", "señal", "sugiere".
Nunca: "va a ganar", "es fijo", "el over entra seguro".

---

## 2. When to Use / When Not to Use

### Usar cuando:
- El usuario pide análisis de un partido específico de fútbol.
- La consulta incluye equipos, fecha y (opcionalmente) competición.
- Se necesita contexto, forma, jugadores, predicciones ML y recomendaciones.

### No usar cuando:
- El partido está `inprogress` o `finished` → responder: "Ese partido ya
  comenzó / terminó. Esperá a uno próximo."
- La consulta es sobre un torneo o equipo sin partido específico → no
  procede. Se puede ofrecer buscar próximos partidos de ese equipo.

---

## 3. API Real — Solo lo que la Bzzoiro API soporta

```
GET /api/events/              date_from, date_to, league, status, tz
GET /api/events/{id}/        evento + odds + forma + H2H
GET /api/predictions/         date_from, date_to, league, upcoming, tz
GET /api/predictions/{id}/    UNA predicción por su propio ID
GET /api/player-stats/?event={id}   stats por event ID
GET /api/player-stats/{id}/   un registro individual por su ID
GET /api/teams/{id}/           datos del equipo (sin histórico)
GET /api/leagues/              lista de ligas
```

### Lo que NO existe en la API de fútbol:

| Qué no existe | Consecuencia |
|---|---|
| `GET /api/events/?team=X` | No hay forma de pedir "últimos 10 del Barcelona" directamente. La forma disponible viene en `home_form`/`away_form` del evento. |
| `GET /api/predictions/?event=X` | Las predicciones se listan por fecha+liga y se buscan por `event.id` embebido. |
| Endpoint de corners | La API no provee esquinas. No mencionar. |
| Endpoint de alineaciones anticipadas | `lineups` viene `null` en pre-partido. No usar. |
| Histórico de lesiones | No existe en la API. No inventar. |

**Fuente de cada señal en el análisis:**

| Tag | Significado |
|---|---|
| `[API]` | Dato directo de un endpoint de la API (evento, equipo, liga) |
| `[ML]` | Dato de la predicción ML (`/api/predictions/`) |
| `[ODDS]` | Calculado de cuotas de mercado |
| `[IND]` | Indicador calculado a partir de los datos de la API |
| `[N/A]` | Dato no disponible en la API |

---

## 4. Pipeline de Análisis

### 4.1 Parsing de la consulta

De la consulta en lenguaje natural extraer:

```
{
  home_team:  string,      // equipo mencionado primero
  away_team:  string,       // equipo mencionado segundo (o null si solo uno)
  date_from:  ISO 8601,    // fecha inicio del rango
  date_to:    ISO 8601,    // fecha fin del rango
  league:     string|null   // competición mencionada (o null)
}
```

**Reglas de parsing:**

| Situación | Regla |
|---|---|
| El usuario dice "hoy" | `date_from = hoy`, `date_to = hoy` |
| El usuario dice "mañana" | `date_from = mañana`, `date_to = mañana` |
| El usuario dice "este finde" | `date_from = viernes`, `date_to = domingo` |
| El usuario dice "esta semana" sin día | `date_from = lunes`, `date_to = domingo` |
| Solo un equipo mencionado | Buscar el próximo partido de ese equipo en el rango de 7 días |
| Nombres con acento ("Atletico", "Inter") | Normalizar quitando acentos antes de buscar |
| Nombres parciales ("Barça", "Atleti") | Fuzzy match contra `home_team`/`away_team` del resultado |
| Competición mencionada ("la league", "champions") | Filtrar por `league_id` tras buscar |

**Si solo un equipo matchea pero hay múltiples candidatos del rival:**
→ Clarificación obligatoria. Preguntar: "¿Buscás el [equipo] vs [candidato A] o vs [candidato B]?"

### 4.2 Match Discovery (Fase 1)

```
1.  GET /api/events/?date_from=X&date_to=Y[&league=Z]
    → Si falla: "No pude consultar la API. Verificá conexión."
2.  Normalizar nombres y buscar fuzzy en home_team / away_team
    → Si 0 resultados: "No encontré ningún partido para esas fechas."
    → Si 1 resultado: proceed.
    → Si >1 resultado: clarificación obligatoria.
3.  Verificar estado del evento:
    → status = "notstarted" → proceed.
    → status = "inprogress": "Ese partido ya está en juego."
    → status = "finished":   "Ese partido ya terminó."
```

**Nota sobre fuzzy matching:**
- Intentar primero match exacto (case-insensitive).
- Si no hay exacto, intentar substring.
- Si no, intento sin acentos.
- Si ninguno funciona → "No encontré '[equipo]'. Verificá el nombre."

**Priorización cuando hay múltiples candidatos:**
1. Si el usuario mencionó liga → priorizar esa liga.
2. Si el usuario mencionó fecha exacta → solo considerar esa fecha.
3. Si hay exactamente 1 partido de cada equipo combinado → usar ese.
4. Si no, clarificación obligatoria.

### 4.3 Data Gathering (Fase 2)

**Llamadas obligatorias (si alguna falla, marcar el canal N/A y reducir confianza):**

```
a) GET /api/events/{id}/          → evento + odds + forma + H2H
b) GET /api/predictions/?date_from=X&date_to=Y&league=Z
   → Buscar la predicción donde event.id == partido.id
   → NO usar /api/predictions/{id}/ (ese ID es de la predicción, no del evento)
```

**Llamadas opcionales (si faltan, no bloquean el análisis):**

```
c) GET /api/player-stats/?event={id}   → stats de jugadores (puede estar vacío)
d) GET /api/teams/{home_team_id}/      → solo nombre y país (ya viene en evento)
e) GET /api/teams/{away_team_id}/      → solo nombre y país (ya viene en evento)
```

**Si falla la llamada obligatoria (a) evento:**
→ Análisis no viable. Informar: "No pude obtener los datos del evento."

**Si falla la llamada obligatoria (b) predicción:**
→ Marcar ML como "no disponible [N/A]". Proceder sin Capa 7 predictiva fuerte.
  Ajustar confianza global: máximo media-alta, nunca alta.

**Minimum viable data:**
- Para análisis con 8 capas (degradadas si es necesario): evento + al menos
  odds O predicción ML.
- Para predictiva (Capa 7): necesita al menos odds del evento.
  Si no hay odds ni ML → no emitir lectura de resultado.
- Para prescriptiva (Capa 8): necesita Capa 7 + al menos Capa 2 o Capa 4.
  Si Capa 7 es muy baja confianza → Capa 8 también.

---

## 5. Las 8 Capas — Definición Exacta

Cada capa tiene: inputs, cálculos, output obligatorio, degradación.

---

### Capa 1 — Contexto Base

**Inputs:** `odds_home`, `odds_draw`, `odds_away`, `odds_over_25`,
`odds_btts_yes`, predicción ML (si existe).

**Cálculos:**
- Probabilidad implícita de mercado: `1 / odds`
- Probabilidad implícita Over 2.5: `1 / odds_over_25`
- Probabilidad implícita BTTS: `1 / odds_btts_yes`
- Diferencia mercado vs ML: `prob_ML_home - prob_mercado_home`
- Sesgo: favorito claro (>60%), favorito leve (50-60%), equilibrado (<50%)
- Intensidad estimada: baja (<2.5 xG total), media (2.5-3.5), alta (>3.5)

**Output obligatorio:**
```
## 1. Contexto del Partido
- Partido: [Home] vs [Away]
- Competición: [Liga]
- Fecha/hora: [ISO 8601]
- Estado: [notstarted]
---
Mercado dice [ODDS]:
- [Home]: [prob]% | Draw: [prob]% | [Away]: [prob]%
- Over 2.5: [cuota] → prob implícita [prob]%
- BTTS: [cuota] → prob implícita [prob]%
---
Modelo ML dice [ML]:
- [Home]: [prob]% | Draw: [prob]% | [Away]: [prob]%
- Score más probable: [scoreline]
- Confianza: [prob]%
---
¿Concuerdan? [Sí/No] — [explicación breve, 1-2 líneas]
```

**Degradación:**
- Si no hay ML → omitir sección ML, solo mercado. ¿Concuerdan? → "Sin ML, solo el mercado."
- Si no hay odds → no usar diff mercado vs ML. Usar solo ML.
- Si neither → capa 1 muy degradada.

---

### Capa 2 — Descriptiva de Equipos

**Inputs:** `home_form`, `away_form`, `head_to_head` del evento.

**Cálculos:**
- Puntos últimos N: de `home_form.points_last_n` / `away_form.points_last_n`
- Forma: W/D/L de `home_form.form_string` / `away_form.form_string`
- Goles avg: `goals_scored_last_n / matches_played` y `goals_conceded_last_n / matches_played`
- xG avg: `avg_xg` / `avg_xg_conceded` (si disponible)
- Over 2.5 freq: contar partidos con total > 2.5 en últimos N
- BTTS freq: contar partidos con gol de ambos en últimos N
- Perfil: según xG generado vs goles reales (sobre/sub-reperformance)
- H2H: de `head_to_head` si existe

**Output obligatorio:**
```
## 2. Qué Viene Pasando

[Home] [IND]:
  Forma: [form_string] — [pts] pts / [N] pts posibles
  Goles: [gf_avg]/[gc_avg] | xG: [xG_avg]/[xG_conc_avg] (si disponible)
  Over 2.5: [X/N] | BTTS: [X/N] (si hay datos)
  En casa: [home_ppg] ppg | [home_goals]GF / [home_goals]GC
  Perfil: [ofensivo/conservador/equilibrado/inestable]

[ away ] [IND]:
  [mismo formato]

H2H [IND]: [X]PJ — [home_wins]V [draws]E [away_wins]D | avg goles [avg]
  [score reciente 1]
  [score reciente 2]

Nota: [si la forma se extrajo solo del evento actual (N=1), indicarlo]
```

**Degradación:**
- Si `home_form` viene vacío → solo listar H2H disponible. Forma = N/A.
- Si no hay H2H → omitir sección H2H.
- Siempre incluir la nota si la muestra es N < 5.

---

### Capa 3 — Descriptiva de Jugadores

**Inputs:** `player-stats` para el evento.

**Cálculos por jugador (solo si `count > 0` en player-stats):**
```
Impacto ofensivo  = (goals + xG*0.5 + assists*0.5 + xA*0.3) / mins * 90
Creación          = (key_passes + passes*0.1) / mins * 90
Defensa           = (tackles_won + interceptions + ball_recoveries) / mins * 90
Disciplina        = (yellow_cards + red_cards) / mins * 90   [menor es mejor]
```
Top 3 por equipo por impacto ofensivo.
Alertar si un equipo tiene >40% de su impacto total de equipo en un solo jugador.

**Output obligatorio:**
```
## 3. Protagonistas

[Si count == 0 o no existe player-stats:]
Sin datos suficientes de protagonistas [N/A] — capa degradada.

[Si count > 0:]
[Jugador] ([pos]):
  Impacto: X.X | Creación: X.X | Defensa: X.X

[Top 3 por equipo]

Riesgo disciplinario: [jugadores con índice > 0.5 por partido]
Dependencia excesiva: [equipo] depende de [jugador] (>40% del impacto)
```

**Degradación:**
- Si no hay player-stats → texto obligatorio: "Sin datos suficientes de
  protagonistas [N/A] — capa degradada." No inventar jugadores, alineaciones,
  ni lesionados.

---

### Capa 4 — Indicadores Compuestos

**Inputs:** `home_form`, `away_form`, odds, predicción ML.

**Cálculos:**
- Ventaja ofensiva: `home_form.avg_xg - away_form.avg_xg` (si disponible)
- Fragilidad defensiva: `away_form.avg_xg_conceded / away_form.matches_played`
- Gap forma: `home_form.points_last_n - away_form.points_last_n`
- Gap casa/fuera: `home_form.home_ppg - away_form.away_ppg`
- Riesgo Over 2.5: promedio de freq Over de ambos
- Riesgo BTTS: promedio de freq BTTS de ambos
- Disciplina: promedio de `avg_yellow_cards` de ambos
- Volatilidad: desv. estándar de goles en últimos 5 de cada equipo
- Estabilidad muestra: N partidos disponibles vs mínimo 5

**Coherencia mercado-modelo:**
- **Alta:** mercado y modelo favorecen el mismo lado Y con magnitudes similares
  (diferencia < 10 pts en prob del favorito).
- **Moderada:** coinciden en el lado, difieren en intensidad (10-20 pts).
- **Baja:** favorecen lados distintos, o uno ve equilibrio y el otro no.

**Output obligatorio:**
```
## 4. Indicadores Compuestos

Ventaja ofensiva: [Home] por [+/-X.XX] xG [IND]
Fragilidad: [Away] recibe [X.XX] goles/partido [IND]
Gap forma (últimos [N]): [Home] [+/-X pts] sobre [Away] [IND]
Gap casa/fuera: [Home] [+/-X.X] ppg [IND]
Riesgo Over 2.5: [X%] [IND]
Riesgo BTTS: [X%] [IND]
Volatilidad: [baja/media/alta] [IND]
Índice disciplina: [bajo (<1.0 yc/pp) / medio (1.0-1.5) / alto (>1.5)] [IND]
Mercado vs ML: [alta/moderada/baja]
Estabilidad muestra: [N] partidos / mínimo 5 — [suficiente/limitado]
```

**Degradación:**
- Si no hay xG → omitir ventaja ofensiva y fragilidad.
- Si no hay forma (N<3) → gap forma y volatilidad = N/A.

---

### Capa 5 — Diagnóstica

**Inputs:** output de capas 1, 2 y 4.

**Evaluar:**
1. ¿Resultados respaldados por xG? → sobre/sub-rendimiento real
2. ¿Defensa concede por mérito propio o rivales débiles?
3. ¿Over viene por volumen o por caos defensivo?
4. ¿Favorito del mercado tiene respaldo en indicadores?
5. ¿ML alineado con indicadores?
6. ¿Señales contradictorias?

**Output obligatorio:**
```
## 5. Por Qué Pasa

[Home]: [sobre/sub]-rendimiento — xG ([xG]) vs goles ([G]) indica [explicación]
[Causa de la tendencia]

[Si contradicciones:]
Contradicciones:
- [contradicción 1]
- [contradicción 2]

¿Sostenible? [sí/no] — [tendencia] → [sostenible/ruido]
```

**Degradación:**
- Si no hay xG → omitir evaluación de sobre/sub-rendimiento.
- Si no hay forma → "Datos insuficientes para diagnóstico de tendencia [N/A]."

---

### Capa 6 — Ponderación de Señales

**Reglas de peso:**

| Peso | Qué cuenta | Qué NO cuenta |
|---|---|---|
| **Fuerte** | xG reciente, tiros, consistencia (N≥5), coincidencia mercado-ML, producción jugadores clave | Rachas cortas sin respaldo, marcadores aislados |
| **Moderada** | Forma con N=3-4, H2H sin contexto de local/visita, diff mercado-ML moderada | |
| **Débil** | N<3, diff mercado-ML alta, mercado sin respaldo en ML | |

**Output obligatorio:**
```
## 6. Qué Señales Pesan Más

Fuertes [fuente]:
- [señal + razón]

Moderadas [fuente]:
- [señal + razón]

Débiles [razón]:
- [señal]

No utilizables [razón]:
- [señal]

Outliers:
- [partido + razón]
```

**Degradación:**
- Si Capa 4 no está disponible → señales no utilizables.

---

### Capa 7 — Predictiva

**Reglas de combinación:**

| Condición | Acción |
|---|---|
| ML disponible + indicadores disponibles | Combinar ambos |
| Solo ML disponible | Usar solo ML |
| Solo indicadores disponibles | Usar solo indicadores |
| Ni ML ni indicadores | No emitir predictiva fuerte. Confianza muy baja. |
| Mercado y modelo coinciden | Reforzar señal |
| Contradicción mercado vs ML | Atenuar. Marcar "inseguro". |

**Output obligatorio:**
```
## 7. Qué Podría Pasar

Resultado: [Home] [X]% | Empate [Y]% | [Away] [Z]%
Goles esperados: [Home] [X.XX] | [Away] [Y.XX]
Over 1.5: [X]% | Over 2.5: [Y]% | BTTS: [Z]%
Score más probable: [scoreline]
Tipo: [cerrado/abierto/defensivo/competido]
Confianza: [muy baja/baja/media/media-alta/alta] — [motivo de la calificación]
```

**Degradación:**
- Si ni ML ni odds → "Predictiva no disponible [N/A] — datos insuficientes."
- Si contradicción mercado vs ML → añadir: "⚠ Mercado y modelo no coinciden.
  Incertidumbre elevada."

---

### Capa 8 — Prescriptiva

**Reglas:**
- Emitir 3-5 señales más fuertes (de Capa 6).
- Emitir 2-3 alertas (de Capa 5).
- Mercados con sustento: solo los que tengan respaldo en al menos 2 capas.
- Mercados sin sustento: explicar brevemente por qué.

**Output obligatorio:**
```
## 8. Qué Leer con Mejor Soporte

Señales más fuertes (3-5):
1. [lectura] — respaldada por [fuente 1 + fuente 2]

Alertas (2-3):
⚠ [alerta] — [razón]

Mercados con sustento:
- [mercado] → [razón]

Mercados sin sustento:
- [mercado] — [razón breve]
```

**Degradación:**
- Si Capa 7 es muy baja confianza → Capa 8 se reduce a "Señales más
  fuertes" (sin recomendación de mercados).

---

## 6. Política de Confianza

### Confianza global

| Estado de los datos | Confianza máxima |
|---|---|
| Evento + odds + ML + player-stats + forma | **Alta** |
| Evento + odds + ML (sin player-stats) | **Media-alta** |
| Evento + ML (sin odds) | **Media** |
| Evento + odds (sin ML) | **Media** |
| Evento solo | **Baja** |
| Sin evento | **Muy baja / análisis inviable** |

### Ajuste por capa

| Dato faltante | Capas afectadas | Reducción |
|---|---|---|
| Sin predicción ML | Capa 1, Capa 7 | Máx. media-alta |
| Sin odds | Capa 1, Capa 7 | Máx. media |
| Sin xG | Capa 4, Capa 5 | Señales de gol debilitadas |
| Sin player-stats | Capa 3 | Solo texto N/A |
| Sin forma (N<3) | Capa 2, Capa 4 | Datos históricos no disponibles |
| Sin H2H | Capa 2 | H2H = N/A |

### Por capa

Cada capa puede marcarse como:
- **Completa** — todos los inputs disponibles.
- **Parcial** — algunos inputs faltantes, se usa texto [N/A] correspondiente.
- **No disponible** — inputs requeridos faltantes, no se puede calcular.

---

## 7. Anti-Racionalizaciones

Esta es la sección de guardrails. Es de cumplimiento **obligatorio**.
Todo lo que sigue **no se puede hacer**, sin excepción:

### No inventar datos
- `[N/A]` → **no inventar.** Si no hay player-stats → capa 3 = "Sin datos
  suficientes." Si no hay xG → "xG no disponible [N/A]."
- No inventar alineaciones, lesionados, sancionados, técnicos.
- No inventar H2H si `head_to_head` viene vacío o null.
- No inventar corners. La API no los provee.

### No usar fuentes externas
- No consultar SofaScore, Flashscore, Transfermarkt, Wikipedia, RapidAPI,
  ni ninguna otra fuente durante el análisis.
- La única fuente válida es la Bzzoiro API.

### No improvisar modelos
- No construir un modelo heurístico para reemplazar la predicción ML de la API.
- Si la predicción ML no está disponible → trabajar solo con odds e indicadores.
- Las probabilidades en Capa 7 vienen de ML u odds. No de cuentas propias.

### No vender certeza
- No decir "va a ganar", "es fijo", "el over entra seguro".
- Siempre decir "podría", "señal", "sugiere", "la evidencia apunta a".
- Siempre indicar confianza.

### No omitir contradicciones
- Si mercado y ML favorecen lados distintos → decirlo explícitamente.
- Si una señal es ruido y no tendencia → decirlo.

### No rellenar con frases vacías
- Cada sección tiene output definido con campos obligatorios.
- Si no hay dato para un campo → "[N/A]" + razón breve.
- No dejar una sección "blanca" ni con frases genéricas que no dicen nada.

### No interpretar mal la API
- La API no tiene `/api/events/?team=X`. No existe.
- La API no tiene `/api/predictions/{event_id}/`. El ID de predicción ≠ event_id.
- La API devuelve `notstarted` (no `inprogress`) para partidos por jugarse.

---

## 8. Formato de Salida del Análisis

**Estructura obligatoria (en este orden exacto):**

```
# [Home] vs [Away] — [Competición] ([Fecha])

[8 capas completas]

---
Confianza global: [muy baja/baja/media/media-alta/alta]
```

**Longitud orientativa por sección:**
- Capas 1-2: 8-15 líneas cada una.
- Capas 3-6: 5-12 líneas cada una.
- Capas 7-8: 8-15 líneas cada una.

**Datos no disponibles:**
- Siempre usar `[N/A]` para datos faltantes.
- Siempre explicar brevemente por qué.

**Señales fuertes / moderadas / débiles:**
- Presentar como lista con viñeta, no en prosa.

**Cierre del análisis:**
- Siempre incluir la confianza global.
- Siempre distinguir entre señal fuerte y correlación débil.
- Nunca cerrar con una frase determinista.

### Guardado de datos
1. Guardar este análisis en un txt en ./claude/skills/football-betting-analysis/football-analysis.
2. Crear una carpeta cuyo nombre corresponda con el nombre de la competición, por ejemplo, Champions League 25-26.
3. Guardar el archivo como [DD_MM_AAAA] [EQUIPO LOCAL] vs [EQUIPO VISITANTE] [JORNADA_X].txt donde X en [JORNADA_X] es el # de la jornada que se juega o si es 1/4 de final u 1/8, lo que corresponda.

---

## 9. Quick Reference

```
CONSULTA NL → parsing → { home, away, date_from, date_to, league? }

BASE URL:   https://sports.bzzoiro.com
AUTH:       Authorization: Token <bzzoiro_token>

 Match discovery:  GET /api/events/?date_from=X&date_to=Y[&league=Z]
 Evento completo:  GET /api/events/{id}/
 Predicción ML:    GET /api/predictions/?date_from=X&date_to=Y&league=Z
                   → buscar donde event.id == partido.id
 Player stats:     GET /api/player-stats/?event={id}
 Equipos:          GET /api/teams/{id}/

NO EXISTE:
  /api/events/?team=X
  /api/predictions/{event_id}/
```

**Umbrales de confianza:**

| Datos | Confianza máx. |
|---|---|
| Evento + odds + ML + forma | Alta |
| Evento + odds + ML | Media-alta |
| Evento + ML (sin odds) | Media |
| Evento + odds (sin ML) | Media |
| Evento solo | Baja |
| Sin evento | Inviable |

**Etiquetas de fuente obligatorias en todo el análisis:**
`[API]` `[ML]` `[ODDS]` `[IND]` `[N/A]`

---

## 10. Agujeros Cerrados

| Racionalización | Contramedida |
|---|---|
| "Usé SofaScore/RapidAPI porque la Bzzoiro no tenía" | **Prohibido.** Solo Bzzoiro API. Sin excepciones. |
| "No había player-stats así que inventé alineación" | **Prohibido.** Capa 3 = "Sin datos suficientes [N/A]." |
| "Construí un modelo heurístico porque faltaba ML" | **Prohibido.** Usar solo odds e indicadores. No inventar modelos. |
| "El partido ya empezó pero el análisis salió igual" | **Prohibido.** Si status = inprogress/finished → no analizar. |
| "Usé /api/predictions/{event_id}/" | **Prohibido.** Ese endpoint no existe. Buscar por event.id embebido. |
| "El H2H no venía así que puse lo que sabía de memoria" | **Prohibido.** Si head_to_head = null → "H2H no disponible [N/A]." |
| "Le puse 'Alta' aunque solo tenía el evento" | **Prohibido.** Evento solo = confianza Baja. Tabla de umbrales es obligatoria. |
| "El over entra seguro" | **Prohibido.** Lenguaje probabilístico siempre. |
| "Rellené la capa 3 con nombres de memoria" | **Prohibido.** Cada capa tiene output definido. Si no hay datos → [N/A]. |
| "La muestra de 2 partidos es representativa" | **Prohibido.** N<5 = "muestra limitada." Indicadores pesan menos. |
