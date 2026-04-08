---
name: football-betting-analysis
description: >
  Análisis pre-partido de fútbol en 8 capas. Recibe una consulta en lenguaje
  natural, descubre el partido en FlashScore MCP, reúne datos y produce un
  informe estructurado con lenguaje probabilístico. Solo usa FlashScore MCP.
  No inventa datos, no analiza partidos en curso ni finalizados, no suple
  No analiza partidos en curso ni finalizados, no suple la predicción con modelos heurísticos.
---

# Football Betting Analysis

## 1. Overview

Análisis pre-partido de fútbol en 8 capas. Recibe una consulta en lenguaje
natural, descubre el partido en FlashScore MCP, reúne datos y produce un
informe estructurado con lenguaje probabilístico.

El análisis es una interpretación de la evidencia disponible. No es un pick.
No es una garantía. Siempre usa lenguaje como "podría", "señal", "sugiere".
Nunca: "va a ganar", "es fijo", "el over entra seguro".

---

## 2. When to Use / When Not to Use

### Usar cuando:

- El usuario pide análisis de un partido específico de fútbol.
- La consulta incluye equipos, fecha y (opcionalmente) competición.
- Se necesita contexto, forma, jugadores, indicadores y recomendaciones.

### No usar cuando:

- El partido está `inprogress` o `finished` → responder: "Ese partido ya
  comenzó / terminó. Esperá a uno próximo."
- La consulta es sobre un torneo o equipo sin partido específico → no
  procede. Se puede ofrecer buscar próximos partidos de ese equipo.

**Nota arquitectónica:** Esta versión no dispone de predicción basada en modelos
de aprendizaje. Por diseño, la capa predictiva es odds-driven — las probabilidades
numéricas SOLO viennent de odds. Los indicadores solo modulan confianza, no generan
porcentajes.

---

## 3. Fuente de Datos — FlashScore MCP

### Endpoints utilizados

| Endpoint                                     | Uso                                                                                     |
| -------------------------------------------- | --------------------------------------------------------------------------------------- |
| `Get_Matches_by_day` / `Get_Matches_by_date` | Match discovery                                                                         |
| `Get_Match_Details`                          | Evento completo + odds                                                                  |
| `Get_Match_H2H`                              | Head-to-head                                                                            |
| `Get_Match_Stats`                            | Estadísticas del partido (corners, tiros, tiros a puerta, posesión, tarjetas, xG, etc.) |
| `Get_Match_Player_Stats`                     | Stats por jugador                                                                       |
| `Get_Match_Summary`                          | Resumen con eventos clave                                                               |
| `Get_Match_Commentary`                       | Commentary (para contexto de estilo, no como fuente principal)                          |
| `Get_Team_Results`                           | Historial de resultados del equipo                                                      |
| `Get_Team_Fixtures`                          | Próximos partidos del equipo                                                            |
| `Get_Tournament_Standings`                   | Contexto de forma/posición en torneo                                                    |
| `Get_Match_Standings_OverUnder`              | Standings O/U                                                                           |
| `Get_Tournament_Top_Scorers`                 | Goleadores del torneo                                                                   |
| `Get_Match_Standings_Form`                   | Forma reciente dentro del partido                                                       |

### Lo que NO existe en FlashScore (y nunca se debe inventar)

| Qué no existe                        | Consecuencia                                              |
| ------------------------------------ | --------------------------------------------------------- |
| Alineaciones anticipadas confirmadas | Puede venir vacío en pre-partido. No inventar alineación. |
| Histórico de lesiones pre-existentes | No existe en la API. No inventar.                         |

**Fuente de cada señal en el análisis:**

| Tag      | Significado                                         |
| -------- | --------------------------------------------------- |
| `[API]`  | Dato directo de un endpoint de FlashScore MCP       |
| `[ODDS]` | Calculado de cuotas de mercado                      |
| `[IND]`  | Indicador calculado a partir de los datos de la API |
| `[N/A]`  | Dato no disponible en la API                        |

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

| Situación                                         | Regla                                                         |
| ------------------------------------------------- | ------------------------------------------------------------- |
| El usuario dice "hoy"                             | `date_from = hoy`, `date_to = hoy`                            |
| El usuario dice "mañana"                          | `date_from = mañana`, `date_to = mañana`                      |
| El usuario dice "este finde"                      | `date_from = viernes`, `date_to = domingo`                    |
| El usuario dice "esta semana" sin día             | `date_from = lunes`, `date_to = domingo`                      |
| Solo un equipo mencionado                         | Buscar el próximo partido de ese equipo en el rango de 7 días |
| Nombres con acento ("Atletico", "Inter")          | Normalizar quitando acentos antes de buscar                   |
| Nombres parciales ("Barça", "Atleti")             | Fuzzy match contra `home_team`/`away_team` del resultado      |
| Competición mencionada ("la league", "champions") | Filtrar por `league_id` tras buscar                           |

**Si solo un equipo matchea pero hay múltiples candidatos del rival:**
→ Clarificación obligatoria. Preguntar: "¿Buscás el [equipo] vs [candidato A] o vs [candidato B]?"

### 4.2 Match Discovery (Fase 1)

```
1. GET /matches/list-by-date?date=X&sport_id=1
   → Usar rango de fechas si date_from ≠ date_to
   → Si falla: "No pude consultar la API. Verificá conexión."
2. Normalizar nombres y buscar fuzzy en home_team / away_team
   → Si 0 resultados: "No encontré ningún partido para esas fechas."
   → Si 1 resultado: proceed.
   → Si >1 resultado: clarificación obligatoria.
3. Verificar estado del evento:
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
4. **Si múltiples partidos del mismo equipo → priorizar el más cercano en el tiempo al rango de fechas de la consulta.** Esto evita clarificaciones innecesarias.
5. Si no, clarificación obligatoria.

### 4.3 Data Gathering (Fase 2)

**OBLIGATORIA PARA INICIAR (si falla → análisis no viable):**

```
a) Get_Match_Details?match_id=X  → evento + odds
```

**OBLIGATORIAS DE INTENTO (siempre consultar cuando match_id / team_id / tournament_id esté disponible; si falla → [N/A] + degradar solo capa afectada):**

```
b) Get_Match_H2H?match_id=X              → Head-to-head
c) Get_Match_Stats?match_id=X             → stats del partido (corners, tiros, posesión, tarjetas, xG)
d) Get_Match_Player_Stats?match_id=X     → stats por jugador
e) Get_Match_Commentary?match_id=X       → commentary (estilo, contexto)
f) Get_Team_Results?team_id=X            → historial de resultados del equipo
g) Get_Tournament_Standings?tournament_id=X → posición en torneo
```

**REGLA GENERAL:**

- Si alguno de estos endpoints devuelve datos → incorporarlos al análisis.
- Si devuelve vacío, null, error o no aplica en pre-partido → marcar `[N/A]` y degradar solo la capa afectada.
- La ausencia de datos **no autoriza a inventarlos** ni a sustituirlos con fuentes externas.
- Sin evento (Get_Match_Details) no hay análisis; sin H2H puede haber análisis degradado.

**Si falla OBLIGATORIA PARA INICIAR (a) evento:**
→ Análisis no viable. Informar: "No pude obtener los datos del evento."

**Si falla OBLIGATORIA DE INTENTO (b-g):**
→ Datos = [N/A]. Degradar solo la capa que dependía de ese endpoint.
No inventar, no sustituir con fuentes externas.

**Minimum viable data:**

- Para análisis con 8 capas (degradadas si es necesario): evento + al menos odds.
- Para predictiva (Capa 7): necesita odds del evento. Si no hay odds → no emitir lectura.
- Para prescriptiva (Capa 8): necesita Capa 7 + al menos Capa 2 o Capa 4.
  Si Capa 7 es muy baja confianza → Capa 8 también.

**Priorización cuando hay múltiples matches del mismo equipo:**
→ Si hay múltiples partidos del mismo equipo, priorizar el más cercano
en el tiempo al rango de fechas de la consulta. Esto evita clarificaciones
innecesarias.

---

## 5. Las 8 Capas — Definición Exacta

Cada capa tiene: inputs, cálculos, output obligatorio, degradación.

---

### Capa 1 — Contexto Base

**Inputs:** `odds_home`, `odds_draw`, `odds_away`, `odds_over_25`,
`odds_btts_yes`.

**Cálculos:**

- Probabilidad implícita de mercado: `1 / odds`
- Probabilidad implícita Over 2.5: `1 / odds_over_25`
- Probabilidad implícita BTTS: `1 / odds_btts_yes`
- Sesgo: favorito claro (>60%), favorito leve (50-60%), equilibrado (<50%)

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
Indicadores históricos [IND]:
- Indicadores favorecen: [Home/Away/Equilibrado]
- Soporte histórico: [bajo/medio/alto]
Mercado vs datos: [alineados/parcialmente alineados/en conflicto] — [explicación breve]
```

**Degradación:**

- Si no hay odds → no usar diff mercado vs indicadores. Usar solo odds si disponibles.
- Si neither → capa 1 muy degradada.

---

### Capa 2 — Descriptiva de Equipos

**Inputs:** `Get_Team_Results` (historial), `Get_Match_H2H`, `Get_Tournament_Standings` (si aplica).

**Cálculos:**

- Puntos últimos N: de resultados del equipo
- Forma: resultados recientes (W/D/L)
- Goles avg: `goals_scored / matches_played` y `goals_conceded / matches_played`
- Over 2.5 freq: contar partidos con total > 2.5 en últimos N
- BTTS freq: contar partidos con gol de ambos en últimos N
- Perfil: según goles generados vs goles reales (sobre/sub-reperformance)
- H2H: de `Get_Match_H2H` si existe

**Output obligatorio:**

```
## 2. Qué Viene Pasando

[Home] [IND]:
  Forma: [form_string] — [pts] pts / [N] pts posibles
  Goles: [gf_avg]/[gc_avg]
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

### Capa 3 — Protagonistas

**Inputs directos de `Get_Match_Player_Stats`:**
`goals`, `assists`, `shots`, `shots_on_target`, `key_passes`,
`tackles_won`, `interceptions`, `ball_recoveries`, `yellow_cards`,
`red_cards`, `minutes`.

**Reglas — SIN fórmulas heurísticas:**

- No usar pesos (0.3, 0.5, etc.) ni normalizaciones inventadas.
- No calcular "impact score", "impacto ofensivo", ni ninguna métrica compuesta.
- **Sí se permite:** ranking directo por métrica individual (más goles, más pases clave, etc.).
- **Dependencia:** proporción directa de goles/producción del jugador vs total del equipo.

**Outputs por jugador (datos directos, sin fórmulas):**

```
[Jugador X] ([pos]):
  Producción:
  - Goles: X
  - Asistencias: X

  Volumen ofensivo:
  - Tiros: X (X a puerta)

  Creación:
  - Pases clave: X

  Disciplina:
  - Amarillas: X | Rojas: X
```

**Top N por equipo (ranking directo por métrica — sin scores compuestos):**

```
Top generadores de gol [IND]:
1. [Jugador A] — [X] goles
2. [Jugador B] — [X] goles

Top creadores [IND]:
1. [Jugador A] — [X] pases clave
2. [Jugador B] — [X] pases clave
```

**Dependencia ofensiva:**

- Calcular: `(goles jugador / total goles equipo) * 100`
- Umbral: >40% → "Dependencia ofensiva alta [IND]"
- Si un equipo tiene >50% de producción en un solo jugador → alertar.

**Commentary (uso regulado):**

- Commentary solo es válido si **coincide con indicadores de otras capas**.
- No usar commentary como señal principal ni sobreinterpretar eventos aislados.
- Si commentary describe un patrón no respaldado por stats → omitir o marcar como "dato observacional no concluyente".

**Output obligatorio:**

```
## 3. Protagonistas

[Si no hay player-stats:]
Sin datos disponibles de protagonistas [N/A] — capa degradada.

[Si hay datos:]
[Jugador] ([pos]):
  Producción:
  - Goles: X
  - Asistencias: X
  Volumen ofensivo:
  - Tiros: X (X a puerta)
  Creación:
  - Pases clave: X
  Disciplina:
  - Amarillas: X | Rojas: X

[Top del partido]

Dependencia ofensiva:
- [Equipo]: [jugador] → [X]% de los goles del equipo [IND]

[Si commentary disponible Y coincide con indicadores:]
Patrón de estilo observado: [descripción]

[Si commentary disponible pero NO coincide con indicadores:]
Patrón de estilo: [N/A] — dato observacional no respaldado por stats.
```

**Degradación:**

- Si no hay player-stats → texto obligatorio: "Sin datos suficientes de
  protagonistas [N/A] — capa degradada." No inventar jugadores, alineaciones,
  ni lesionados.

---

### Capa 4 — Indicadores Compuestos

**Inputs:** stats de partido (`Get_Match_Stats`), historial de equipos (`Get_Team_Results`), odds.

**Cálculos:**

- Ventaja ofensiva: diferencia de goles avg entre equipos
- Fragilidad defensiva: goles recibidos / partidos jugados del equipo visitante
- Gap forma: puntos últimos N de cada equipo
- Gap casa/fuera: PPG home vs PPG away
- Riesgo Over 2.5: promedio de freq Over de ambos
- Riesgo BTTS: promedio de freq BTTS de ambos
- Disciplina: promedio de tarjetas de ambos equipos (de `Get_Match_Stats`)
- Volatilidad: desv. estándar de goles en últimos 5 de cada equipo
- Estabilidad muestra: N partidos disponibles vs mínimo 5

**Coherencia mercado-datos:**

- **Alta:** mercado y datos históricos favorecen el mismo lado Y con magnitudes similares.
- **Moderada:** coinciden en el lado, difieren en intensidad.
- **Baja:** favorecen lados distintos, o uno ve equilibrio y el otro no.

**Output obligatorio:**

```
## 4. Indicadores Compuestos

Ventaja ofensiva: [Home] por [+/-X.XX] goles [IND]
Fragilidad: [Away] recibe [X.XX] goles/partido [IND]
Gap forma (últimos [N]): [Home] [+/-X pts] sobre [Away] [IND]
Gap casa/fuera: [Home] [+/-X.X] ppg [IND]
Riesgo Over 2.5: [X%] [IND]
Riesgo BTTS: [X%] [IND]
Volatilidad: [baja/media/alta] [IND]
Índice disciplina: [bajo (<1.0 yc/pp) / medio (1.0-1.5) / alto (>1.5)] [IND]
Mercado vs datos: [alta/moderada/baja]
Estabilidad muestra: [N] partidos / mínimo 5 — [suficiente/limitado]
```

**Degradación:**

- Si no hay forma (N<3) → gap forma y volatilidad = N/A.

---

### Capa 5 — Diagnóstica

**Inputs:** output de capas 1, 2 y 4, `Get_Match_Commentary` (si disponible).

**Regla sobre commentary:**

- Commentary **solo es válido si coincide con indicadores de otras capas**.
- No usar commentary como señal principal.
- No sobreinterpretar eventos aislados.
- Si commentary describe un patrón no respaldado por stats → omitir o marcar como "dato observacional no concluyente".

**Evaluar:**

1. ¿Resultados respaldados por stats de tiros? → sobre/sub-rendimiento real
2. ¿Defensa concede por mérito propio o rivales débiles?
3. ¿Over viene por volumen o por caos defensivo?
4. ¿Favorito del mercado tiene respaldo en indicadores?
5. ¿Señales contradictorias?
6. ¿El estilo de partido se identifica en commentary? (caos, dominio de esquinas, volumen de llegadas)

**Output obligatorio:**

```
## 5. Por Qué Pasa

[Home]: [sobre/sub]-rendimiento — goles vs stats indica [explicación]
[Causa de la tendencia]

[Si commentary disponible Y coincide con indicadores de otras capas:]
Patrón de estilo: [según lo que surja del commentary — caos/defensivo/abierto/competido]

[Si commentary disponible pero NO coincide con indicadores:]
Patrón de estilo: [N/A] — dato observacional no respaldado por stats.

[Si contradicciones:]
Contradicciones:
- [contradicción 1]
- [contradicción 2]

¿Sostenible? [sí/no] — [tendencia] → [sostenible/ruido]
```

**Degradación:**

- Si no hay stats → omitir evaluación de sobre/sub-rendimiento.
- Si no hay forma → "Datos insuficientes para diagnóstico de tendencia [N/A]."

---

### Capa 6 — Ponderación de Señales

**Reglas de peso:**

| Peso         | Qué cuenta                                                                              | Qué NO cuenta                                   |
| ------------ | --------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Fuerte**   | Tiros, consistencia (N≥5), coincidencia mercado-indicadores, producción jugadores clave | Rachas cortas sin respaldo, marcadores aislados |
| **Moderada** | Forma con N=3-4, H2H sin contexto de local/visita, diff mercado-historial moderada      |                                                 |
| **Débil**    | N<3, diff mercado-historial alta, mercado sin respaldo en indicadores                   |                                                 |

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

### Capa 7 — Predictiva (odds-driven)

**Reglas de combinación:**

| Condición                            | Acción                                                        |
| ------------------------------------ | ------------------------------------------------------------- |
| Odds disponibles                     | Usar odds como fuente base de probabilidades                  |
| Indicadores disponibles              | Solo para subir/bajar confianza, no para inventar porcentajes |
| Ni odds ni indicadores               | No emitir predictiva. Confianza muy baja.                     |
| Mercado y datos históricos coinciden | Reforzar señal                                                |
| Contradicción mercado vs historial   | Atenuar. Marcar "inseguro".                                   |

**Las probabilidades numéricas SOLO pueden salir de odds. Los indicadores NO crean porcentajes.**

**Output obligatorio:**

```
## 7. Qué Podría Pasar

Resultado: [Home] [X]% | Empate [Y]% | [Away] [Z]%
Goles esperados: [Home] [X.XX] | [Away] [Y.XX] (basado en avg histórico)
Over 1.5: [X]% | Over 2.5: [Y]% | BTTS: [Z]%
Tipo: [cerrado/abierto/defensivo/competido]
Confianza: [muy baja/baja/media/media-alta/alta] — [motivo de la calificación]

Nota: "Predictiva basada en odds y stats históricas."
```

**Degradación:**

- Si ni odds ni indicadores → "Predictiva no disponible [N/A] — datos insuficientes."
- Si contradicción mercado vs historial → añadir: "⚠ Mercado y datos históricos no coinciden.
  Incertidumbre elevada."

---

### Capa 8 — Prescriptiva Ligera

**Reglas:**

- Emitir 3-5 señales más fuertes (de Capa 6).
- Emitir 2-3 alertas (de Capa 5).
- Mercados con sustento: solo los que tengan respaldo en al menos 2 capas.
- Mercados sin sustento: explicar brevemente por qué.
- **Tono cauteloso:** Usar siempre la frase
  "lecturas mejor soportadas por la evidencia disponible".

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

Nota: "Las lecturas anteriores son las mejor soportadas por la evidencia
disponible."
```

**Degradación:**

- Si Capa 7 es muy baja confianza → Capa 8 se reduce a "Señales más
  fuertes" (sin recomendación de mercados).

---

## 6. Política de Confianza

### Confianza global

| Estado de los datos                              | Confianza máxima                 |
| ------------------------------------------------ | -------------------------------- |
| Evento + odds + stats + player-stats + historial | **Alta**                         |
| Evento + odds + stats (sin player-stats)         | **Media-alta**                   |
| Evento + odds (sin stats)                        | **Media**                        |
| Evento solo                                      | **Baja**                         |
| Sin evento                                       | **Muy baja / análisis inviable** |

### Ajuste por capa

| Dato faltante                  | Capas afectadas | Reducción                       |
| ------------------------------ | --------------- | ------------------------------- |
| Sin odds                       | Capa 1, Capa 7  | Máx. media                      |
| Sin stats (tiros, corners, xG) | Capa 4, Capa 5  | Señales de gol debilitadas      |
| Sin player-stats               | Capa 3          | Solo texto N/A                  |
| Sin historial (N<3)            | Capa 2, Capa 4  | Datos históricos no disponibles |
| Sin H2H                        | Capa 2          | H2H = N/A                       |

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

- `[N/A]` → **no inventar.** Si no hay player-stats → capa 3 = "Sin datos suficientes."
- No inventar alineaciones, lesionados, sancionados, técnicos.
- No inventar H2H si `Get_Match_H2H` viene vacío o null.

### No usar fuentes externas

- No consultar Bzzoiro, SofaScore, Transfermarkt, Wikipedia, ni ninguna otra
  fuente durante el análisis.
- La única fuente válida es FlashScore MCP (a través de los endpoints listados
  en sección 3).

### No improvisar modelos

- No construir un modelo heurístico para reemplazar la predicción basada en modelos de aprendizaje.
- Esta versión es odds-driven por diseño. No improvisar modelo propio.
- Las probabilidades numéricas en Capa 7 SOLO viennent de odds. No de cuentas propias.
- No usar pesos (0.3, 0.5, etc.) ni métricas compuestas en Capa 3.

### No vender certeza

- No decir "va a ganar", "es fijo", "el over entra seguro".
- Siempre decir "podría", "señal", "sugiere", "la evidencia apunta a".
- Siempre indicar confianza.

### No omitir contradicciones

- Si mercado e indicadores favorecen lados distintos → decirlo explícitamente.
- Si una señal es ruido y no tendencia → decirlo.

### No rellenar con frases vacías

- Cada sección tiene output definido con campos obligatorios.
- Si no hay dato para un campo → "[N/A]" + razón breve.
- No dejar una sección "blanca" ni con frases genéricas que no dicen nada.

### No interpretar mal FlashScore MCP

- `Get_Matches_by_day` / `Get_Matches_by_date` es la vía de match discovery.
  No existe `/api/events/?team=X`.
- El estado de partido para pre-partido es `notstarted`. Si viene `inprogress` o
  `finished` → no analizar.

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

 Match discovery:   Get_Matches_by_day / Get_Matches_by_date
 Evento + odds:    Get_Match_Details?match_id=X
 H2H:              Get_Match_H2H?match_id=X
 Stats:            Get_Match_Stats?match_id=X
 Player stats:     Get_Match_Player_Stats?match_id=X
 Commentary:       Get_Match_Commentary?match_id=X
 Historial equipo: Get_Team_Results?team_id=X
 Forma/posición:   Get_Tournament_Standings?tournament_id=X

OBLIGATORIA PARA INICIAR:  Get_Match_Details (sin evento → no hay análisis)
OBLIGATORIAS DE INTENTO:   Get_Match_H2H, Get_Match_Stats, Get_Match_Player_Stats,
                           Get_Match_Commentary, Get_Team_Results,
                           Get_Tournament_Standings
                           (si devuelve vacío/null → [N/A] + degradar solo capa afectada)

NO EXISTE EN FLASSCORE:
  Alineaciones anticipadas confirmadas
  Histórico de lesiones pre-existentes
  /api/events/?team=X
```

**Umbrales de confianza:**

| Datos                                            | Confianza máx. |
| ------------------------------------------------ | -------------- |
| Evento + odds + stats + player-stats + historial | Alta           |
| Evento + odds + stats (sin player-stats)         | Media-alta     |
| Evento + odds (sin stats)                        | Media          |
| Evento solo                                      | Baja           |
| Sin evento                                       | Inviable       |

**Etiquetas de fuente obligatorias en todo el análisis:**
`[API]` `[ODDS]` `[IND]` `[N/A]`

---

## 10. Agujeros Cerrados

| Racionalización                                                                                | Contramedida                                                                                                    |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| "Usé Bzzoiro/SofaScore/otra fuente porque FlashScore no tenía"                                 | **Prohibido.** Solo FlashScore MCP. Sin excepciones.                                                            |
| "No había player-stats así que inventé alineación"                                             | **Prohibido.** Capa 3 = "Sin datos suficientes [N/A]."                                                          |
| "Construí un modelo heurístico para reemplazar la predicción basada en modelos de aprendizaje" | **Prohibido.** Capa 7 = odds-driven. No inventar probabilidades.                                                |
| "Usé xG inventado como input"                                                                  | **Prohibido.** Si FlashScore no trae xG en `Get_Match_Stats` → no inventarlo. Usar los datos que la API provee. |
| "El partido ya empezó pero el análisis salió igual"                                            | **Prohibido.** Si status = inprogress/finished → no analizar.                                                   |
| "No había injuries data así que inventé lesionados"                                            | **Prohibido.** FlashScore no tiene injuries histórico. No inventar.                                             |
| "El H2H no venía así que puse lo que sabía de memoria"                                         | **Prohibido.** Si Get_Match_H2H = null → "H2H no disponible [N/A]."                                             |
| "Le puse 'Alta' aunque solo tenía el evento"                                                   | **Prohibido.** Evento solo = confianza Baja. Tabla de umbrales es obligatoria.                                  |
| "El over entra seguro"                                                                         | **Prohibido.** Lenguaje probabilístico siempre.                                                                 |
| "Rellené la capa 3 con nombres de memoria"                                                     | **Prohibido.** Cada capa tiene output definido. Si no hay datos → [N/A].                                        |
| "La muestra de 2 partidos es representativa"                                                   | **Prohibido.** N<5 = "muestra limitada." Indicadores pesan menos.                                               |
| "Calculé un impact score con pesos 0.3/0.5"                                                    | **Prohibido.** Capa 3 usa datos directos y rankings, no fórmulas heurísticas.                                   |
| "Commentary dijo X así que lo uso como señal principal"                                        | **Prohibido.** Commentary solo válido si coincide con indicadores de otras capas.                               |
