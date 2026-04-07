---
name: football-betting-analysis
description: >
  Motor de análisis cuantitativo de fútbol basado en datos de RapidAPI Hub - Free API Live Football Data.
  Usa esta skill cuando el usuario solicite: análisis de partido,pronóstico, predicción descriptiva,
  forma actual de equipo, rendimiento de jugador, estadísticas avanzadas de fútbol,
  comparativa de equipos, H2H, tendencias, patrones, análisis táctico por datos,
  evaluación de rendimiento global vs local, contexto competitivo, o cualquier
  consulta que requiera datos estadísticos de fútbol.

  También activa automáticamente cuando se detecten keywords: partido, Champions,
  Liga, Bayern Madrid, Real Barcelona, forma actual, estadísticas de equipo,
  H2H, antecedentes, over/under, ambos marcan, BTTS, corners, tarjetas,
  clean sheet, streak, tendencia, análisis cuantitativo, predicción,
  rendimiento local/visitante, goleadores, asistente, xG inferido,
  forma recent, ventana móvil, correlación, outlier, análisis de patrón.

  La skill consulta TODOS los datos disponibles de la API: liga doméstica,
  copas nacionales, competiciones europeas y forma individual de jugadores
  para construir una evaluación estadística rigurosa de cada equipo y partido.

  Respeta el rate limit de 1000 requests/hora planificando las llamadas eficientemente.
---

# Football Analysis Engine — Motor de Análisis Cuantitativo

## Propósito y Alcance

Esta skill produce análisis cuantitativos de fútbol fundamentados en datos estadísticos puros,
invocando las APIs de RapidAPI Hub - Free API Live Football Data para construir
una evaluación global de cada equipo, jugador y partido.

El análisis NUNCA se limita a una sola competición. La forma de un equipo se mide cruzando:
- **Liga doméstica** (LaLiga, Bundesliga, Premier League, Serie A, Ligue 1, etc.)
- **Copas nacionales** (Copa del Rey, DFB-Pokal, FA Cup, Coppa Italia, etc.)
- **Competiciones europeas** (Champions League, Europa League, Conference League)
- **Amistosos y pretemporada** cuando sean relevantes

La forma de los jugadores se evalúa cruzando:
- **Goles y asistenciales en todas las competiciones** donde el equipo participa
- **Minutos jugados y estado físico** (lesiones, descansos)
- **Rendimiento en partidos de alta presión** (vs top-10, fuera de casa, derbis)

**Lo que hace:**
- Análisis descriptivo y predicción cuantitativa basada en probabilidades
- Detección de patrones, correlaciones y outliers
- Evaluación robusta de forma con niveles de confianza
- Métricas avanzadas inferidas cuando la API no las provee directamente

---

## Modos de Análisis

### Modo Rápido (~25 llamadas API)
Para consultas directas: "analiza el partido de mañana", "cómo llega [equipo]", "pronóstico [vs]".

Ejecuta: Fases 1 + 2 + 3 (identificación, datos del partido, datos de equipo global).
Output: Resumen estadístico + predicción con confianza.

### Modo Profundo (~80 llamadas API)
Para análisis completos: previas de Champions, finales, El Clasico.
Ejecuta: TODAS las fases.
Output: Análisis completo con correlaciones, outliers, patrones, EDA, y predicción robustecida.

---

## Rate Limiting — Prioridad de Llamadas

**Límite**: 1000 requests/hora. Planifica las llamadas por prioridad:

### Fase 1 — Identificación (máx. 10 calls)
```
1. Get_Search_All → match ID exacto
2. Get_MatchesEvents_by_Date → confirmar fecha y hora
```

### Fase 2 — Datos del Partido (máx. 15 calls)
```
3.  Get_MatchEvent_Score_by_Event_ID
4.  Get_MatchEvent_All_Stats_by_Event_ID    → estadísticas completas
5.  Get_MatchEvent_Status_by_Event_ID
6.  Get_MatchEvent_Detail_by_Event_ID       → detalle eventos
7.  Get_MatchEvent_Highlights_by_Event_ID  → highlights si ya jugado
8.  Get_MatchEvent_Location_by_Event_ID
9.  Get_MatchEvent_Referee_by_Event_ID     → relevante tarjetas/corners
10. Get_MatchEvent_FirstHalf_Stats_by_Event_ID
11. Get_MatchEvent_SecondHalf_Stats_by_Event_ID
12. Get_Head_to_Head_by_Event_ID            → H2H completo
```

### Fase 3 — Datos de Equipo Global (máx. 20 calls)
```
13. Get_Team_Detail_by_Team_ID (x2)
14. Get_Teams_All_List_by_League_ID (x2)
15. Get_Players_List_All_by_Team_ID (x2)
16. Get_Top_Players_by_Goals (leagueId domésticas)
17. Get_Top_Players_by_Assists (leagueId)
18. Get_Top_Players_by_Rating (leagueId)
```

### Fase 4 — Standings y Posición de Liga (máx. 10 calls)
```
19. Get_Standing_All_by_League_ID (x2)
20. Get_Standing_Home_by_League_ID (x2)
21. Get_Standing_Away_by_League_ID (x2)
22. Get_Rounds_All_by_League_ID (x2)
23. Get_Rounds_Detail_by_Round_ID
```

### Fase 5 — Competiciones Adicionales (máx. 20 calls)
```
24. Get_League_Detail_by_League_ID
25. Get_Popular_Leagues
26. Get_All_Seasons
27. Get_Teams_Home_List_by_League_ID (x2)
28. Get_Teams_Away_List_by_League_ID (x2)
```

### Fase 6 — Forma Reciente y News (máx. 15 calls)
```
29. Get_LivescoresMatchesEvents
30. Get_Trending_News
31. Get_News_League_by_League_ID
32. Get_News_Team_by_Team_ID (x2)
33. Get_News_Player_by_Player_ID
```

### Fase 7 — Transfers y Forma Física (máx. 10 calls)
```
34. Get_Top_Transfers
35. Get_Top_Market_Value_Transfers
36. Get_All_Transfers
37. Get_Transfers_by_League_ID (x2)
```

**Total máximo por análisis completo: ~80 calls**

---

## RapidAPI Hub — Free API Live Football Data

### TODOS los Endpoints Disponibles

#### PARTIDOS Y EVENTOS
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_MatchesEvents_by_Date` | `date` (YYYYMMDD) | Todos los partidos de una fecha |
| `Get_League_MatchesEvents_by_Date` | `date`, `leagueId` | Partidos de liga específica por fecha |
| `Get_All_MatchesEvents_by_League_ID` | `leagueId` | Todos los partidos de una competición |
| `Get_LivescoresMatchesEvents` | ninguna | Partidos en vivo ahora mismo |
| `Get_MatchEvent_Score_by_Event_ID` | `eventId` | Marcador de un partido |
| `Get_MatchEvent_Status_by_Event_ID` | `eventId` | Estado (programado, vivo, finalizado) |
| `Get_MatchEvent_Detail_by_Event_ID` | `eventId` | Detalle completo (goles, assist, tarjetas...) |
| `Get_MatchEvent_All_Stats_by_Event_ID` | `eventId` | TODAS las estadísticas del partido |
| `Get_MatchEvent_FirstHalf_Stats_by_Event_ID` | `eventId` | Estadísticas 1ª mitad |
| `Get_MatchEvent_SecondHalf_Stats_by_Event_ID` | `eventId` | Estadísticas 2ª mitad |
| `Get_MatchEvent_Highlights_by_Event_ID` | `eventId` | Highlights del partido |
| `Get_MatchEvent_Location_by_Event_ID` | `eventId` | Ubicación/estadio del partido |
| `Get_MatchEvent_Referee_by_Event_ID` | `eventId` | Árbitro del partido |

#### COMPETICIONES
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_Leagues_List_All` | ninguna | Lista completa de ligas |
| `Get_Leagues_List_All_with_Countries` | ninguna | Ligas con países |
| `Get_Popular_Leagues` | ninguna | ligas populares (UCL, Premier, etc.) |
| `Get_League_Detail_by_League_ID` | `leagueId` | Detalle de una competición |
| `Get_League_Logo_by_League_ID` | `leagueId` | Logo de la competición |
| `Get_All_Football_Countries` | ninguna | Lista de países con fútbol |
| `Get_All_Seasons` | ninguna | Todas las temporadas disponibles |
| `Get_Trophies_All_Seasons_by_League_ID` | `leagueId` | Trofeos por temporada |
| `Get_Trophies_Detail_by_League_ID` | `leagueId`, `season` | Detalle trofeos temporada |
| `Get_Rounds_All_by_League_ID` | `leagueId` | Todas las jornadas/ronde |
| `Get_Rounds_Detail_by_Round_ID` | `roundId` | Detalle de una jornada |
| `Get_Rounds_players_by_League_ID` | `leagueId` | Jugadores de la jornada |

#### EQUIPOS
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_Team_Detail_by_Team_ID` | `teamId` | Info completa de un equipo |
| `Get_Team_Logo_by_Team_ID` | `teamId` | Logo del equipo |
| `Get_Teams_All_List_by_League_ID` | `leagueId` | Todos los equipos de una liga |
| `Get_Teams_Home_List_by_League_ID` | `leagueId` | Equipos que juegan local |
| `Get_Teams_Away_List_by_League_ID` | `leagueId` | Equipos que juegan visitante |
| `Get_Team_Contract_Extension_Transfers_by_Team_ID` | `teamId` | Renovaciones |
| `Get_Team_Players_in_Transfers_by_Team_ID` | `teamId` | Jugadores que llegaron |
| `Get_Team_Players_Out_Transfers_by_Team_ID` | `teamId` | Jugadores que salieron |

#### JUGADORES
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_Player_Detail_by_Player_ID` | `playerId` | Detalle de un jugador |
| `Get_Player_Image_by_Player_ID` | `playerId` | Imagen del jugador |
| `Get_Players_List_All_by_Team_ID` | `teamId` | Plantilla completa |
| `Get_Top_Players_by_Goals` | `leagueId` | Máximo goleador de la competición |
| `Get_Top_Players_by_Assists` | `leagueId` | Máximo asistente de la competición |
| `Get_Top_Players_by_Rating` | `leagueId` | Mejor valorado |
| `Get_Search_All_Players` | `search` | Buscar jugador por nombre |

#### STANDINGS Y ESTADÍSTICAS
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_Standing_All_by_League_ID` | `leagueId` | Clasificación general |
| `Get_Standing_Home_by_League_ID` | `leagueId` | Clasificación local (solo casa) |
| `Get_Standing_Away_by_League_ID` | `leagueId` | Clasificación visitante (solo fuera) |
| `Get_Statistics_Event_by_Event_ID` | `eventId` | Estadísticas event-level |
| `Get_Statistics_First_Half_Event_by_Event_ID` | `eventId` | Stats 1ª mitad |
| `Get_Statistics_Second_Half_Event_by_Event_ID` | `eventId` | Stats 2ª mitad |

#### H2H Y BÚSQUEDA
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_Head_to_Head_by_Event_ID` | `eventId` | H2H entre dos equipos |
| `Get_Search_All` | `search` | Buscar cualquier cosa |
| `Get_Search_Teams` | `search` | Buscar equipo |
| `Get_Search_Players` | `search` | Buscar jugador |
| `Get_Search_Leagues` | `search` | Buscar liga |
| `Get_Search_Matches` | `search` | Buscar partido |

#### NEWS Y TRANSFERS
| Endpoint | Parámetros | Descripción |
|----------|------------|-------------|
| `Get_Trending_News` | ninguna | Noticias trending |
| `Get_News_League_by_League_ID` | `leagueId`, `page` | Noticias de una competición |
| `Get_News_Team_by_Team_ID` | `teamId`, `page` | Noticias de un equipo |
| `Get_News_Player_by_Player_ID` | `playerId`, `page` | Noticias de un jugador |
| `Get_All_Transfers` | `page` | Lista de todos los transfers |
| `Get_Transfers_by_League_ID` | `leagueId` | Transfers de una liga |
| `Get_Top_Transfers` | `page` | Top transfers |
| `Get_Top_Market_Value_Transfers` | `page` | Transfers de mayor valor de mercado |

#### LIGAS COMUNES — IDs de referencia
```
Champions League:    leagueId = 42
Premier League:      leagueId = 47
LaLiga:              leagueId = 87
Bundesliga:          leagueId = 54
Serie A:             leagueId = 71
Ligue 1:             leagueId = 53
Europa League:        leagueId = 65
Conference League:    leagueId = 203
Copa del Rey:         leagueId = 0 (verificar)
FA Cup:               leagueId = 0 (verificar)
DFB-Pokal:            leagueId = 0 (verificar)
```

---

## Motor de Análisis Estadístico — Arquitectura

### Principio General

Todo análisis se construye en capas:

```
CAPA 1 — Datos crudos (respuestas de API)
    ↓
CAPA 2 — Indicadores calculados (EDA en memoria)
    ↓
CAPA 3 — Patrones y correlaciones (si modo profundo)
    ↓
CAPA 4 — Outliers identificados y pesados
    ↓
CAPA 5 — Probabilidades estimadas con confianza
    ↓
CAPA 6 — Output: Predicción descriptiva + Statistical Insights
```

**Regla de hierro**: Cada capa reutiliza datos de la capa anterior.
Nunca repetir llamadas a la API para obtener el mismo dato.

---

## Taxonomía de Datos — Procedencia y Confianza

**OBLIGATORIO**: Antes de usar cualquier métrica en el análisis, clasificar siempre
según esta tabla. Marcar el origen correspondiente en el output.

### Clasificación de Datos

| Tipo | Símbolo | Definición | Ejemplos |
|------|---------|------------|----------|
| **Dato directo de API** | `[API]` | Respuesta literal de un endpoint de la API, sin manipulación | Marcador final, V-E-D de un partido, nombre de jugador, leagueId, fecha |
| **Dato derivado** | `[DER]` | Calculado directamente a partir de datos `[API]` con operación matemática simple (suma, división, promedio) | GF90 = GF / PJ; Win% = V / PJ; GDR = GF90 - GC90 |
| **Dato inferido con media confianza** | `[INF-M]` | Estimado a partir de datos `[API]` que requieren una inferencia razonable. Margen de error +-15% | Corner rate estimado si no viene en stats; forma local/visitante si no se específica claramente en API |
| **Dato inferido con baja confianza** | `[INF-B]` | Estimado a partir de correlaciones o patrones asumidos. Margen de error +-30% o mayor | xG inferido de tiros y distancia; forma vs Top-10 si ranking no es explícito |
| **Dato no disponible** | `[N/A]` | La API no provee este dato y no puede inferirse con Methode razonable | xG real, PPDA, possession value, SCA/GCA reales |

### Reglas de Uso

```
1. PRIORIDAD: [API] > [DER] > [INF-M] > [INF-B] > [N/A]
   Siempre usar el tipo de mayor prioridad disponible.

2. ETIQUETADO: Toda métrica en el output debe tener su símbolo:
   "GF90: 1.73 [DER]" o "xG inferido: 1.4 [INF-B]"

3. INF-B CON CAUTELA: Datos [INF-B] solo para contextualizar.
   No basar predicciones principales en ellos sin corroborar con [API] o [DER].

4. N/A EXPLÍCITO: Si el output requiere [N/A], escribir:
   "xG real: [N/A] — métrica no disponible en API ni inferible"

5. VALIDEZ DE Muestra: Si N < 5, agregar nota:
   "[INF-B] — muestra muy pequeña (N=X), margen de error alto"
```

### Ejemplos de Clasificación

| Métrica reportada | Tipo | Por qué |
|------------------|------|---------|
| "Real Madrid 2-1 Bayern (8 May 2024)" | [API] | Directo de Get_Head_to_Head_by_Event_ID |
| "Win% global: 65%" | [DER] | 13 victorias / 20 partidos |
| "GF90 como local: 2.1" | [DER] | 21 goles / 10 partidos local |
| "Ritmo de corners: ~5.5 por partido" | [INF-M] | Estimado de stats disponibles, no explícito en API |
| "Over 2.5 en Champions: 70%" | [DER] | 7 over / 10 partidos en UCL — calculable de [API] |
| "xG estimado: 1.8" | [INF-B] | Inferido de goles reales, distancia típica, tipo de asistencia |
| "PPDA real: 8.5" | [N/A] | API no provee passes per defensive action |
| "SCA/GCA reales" | [N/A] | API no provee shot-creating actions |

---

## Capa 2 — Análisis Exploratorio (EDA)

### 2.1 Forma Reciente por Ventanas Móviles

Para cada equipo, calcular indicadores en ventanas de:
- **Últimos 3 partidos**: Forma más reciente (peso más alto)
- **Últimos 5 partidos**: Forma intermedia
- **Últimos 10 partidos**: Tendencia de fondo

```
Indicadores por ventana:
- Win/Draw/Loss rate
- Goles a favor por partido (GF90)
- Goles en contra por partido (GC90)
- Clean sheet rate (CS%)
- Over 2.5 rate (O25%)
- Both Teams Score rate (BTS%)
- Promedio corners por partido (CORNERS90) — si stats disponibles
- Promedio tarjetas (TARJ90)
```

**Cálculo de GF90 / GC90**:
```
GF90 = Σ(goles_a_favor) / partidos_jugados
GC90 = Σ(goles_en_contra) / partidos_jugados
GDR = GF90 - GC90  (Goal Difference Rate)
```

**Validación de muestra**:
- Si ventana < 3 partidos → marcar como "MUY POCA MUESTRA — usar con cautela"
- Si ventana = 3 → poca muestra, sesgo posible
- Si ventana >= 5 → muestra aceptable
- Si ventana >= 10 → muestra robusta

### 2.2 Rendimiento por Contexto

Separar el análisis según contexto:

```
Rendimiento Local = últimos N partidos COMO LOCAL
Rendimiento Visitante = últimos N partidos COMO VISITANTE
Rendimiento vs Top-10 = últimos N partidos vs equipos top 10 de la clasificación
Rendimiento vs Resto = últimos N partidos vs equipos fuera top 10
```

**Por qué importa**: Un equipo puede tener 70% win rate global pero 40% fuera de casa.
No es lo mismo enfrentar al Real Madrid en Bernabéu que en campo neutral.

**Señales de alerta por muestra pequeña**:
- Si < 3 partidos en el contexto evaluado → "Datos insuficientes para este contexto"
- Si todos los rivales fueron top-10 o todos débiles → posible sesgo de selección
- Si el partido a predecir es contexto atípico → reducir confianza

### 2.3 Rendimiento por Competición

Para cada equipo, separar resultados por competición:

```
FORMA GLOBAL PONDERADA = (Forma_Liga × 0.35) + (Forma_Copa × 0.20) + (Forma_Europa × 0.30) + (Forma_Reciente × 0.15)

Donde Forma_N = Win% en últimos N partidos de esa competición
```

**Nota sobre pesos**: Los pesos son aproximados y ajustables según la importancia
relevante del partido (ej: Champions = peso mayor si es fase eliminatoria).

### 2.4 EDA de Jugadores

Para cada jugador clave:

```
Goles_Global = Σ(goles en TODAS las competiciones)
Asist_Global = Σ(asistencias en TODAS las competiciones)
MinTotal = Σ(minutos_jugados)
PartidosJugados = COUNT(partidos con minutos > 0)

G90 = Goles_Global / (MinTotal / 90)   [si MinTotal > 0]
A90 = Asist_Global / (MinTotal / 90)    [si MinTotal > 0]
MinPorPartido = MinTotal / PartidosJugados
RitmoMinutos = MinPorPartido / 90       [ratio, 1.0 = siempre 90 min]
```

**Clasificación del ritmo**:
- RitmoMinutos >= 0.85 → "Ritmo alto — titular indiscutible"
- RitmoMinutos >= 0.60 → "Ritmo medio — titular parcial"
- RitmoMinutos < 0.60 → "Ritmo bajo — rotación / lesión reciente"

---

### 2.5 Perfil de Disciplina y Corners

Agregar esta sección para cada equipo en el análisis.

#### Tarjetas

```
Indicadores de disciplina por ventana:
- Amarillas90 = Σ(amarillas) / partidos_jugados     [DER]
- Rojas90 = Σ(rojas) / partidos_jugados             [DER]
- TARJ90 = Amarillas90 + (2 × Rojas90)            [DER] — indice compuesto
- RojaDirecta% = RojasDirectas / PJ                [DER]
- SegundaAmarilla% = SegundasAmarillas / PJ        [DER]
```

**Clasificación de intensidad**:

| TARJ90 | Clasificación | Descripción |
|--------|-------------|-------------|
| < 2.5 | Disciplina alta | Equipo limpio, pocas bajas por sanción |
| 2.5 – 4.0 | Disciplina normal | Perfil medio de la competición |
| 4.0 – 5.5 | Disciplina baja | Frequent tarjetas, posibles sanciones |
| > 5.5 | Disciplina muy baja | Rouge, posibles bajas de impacto |

**Impacto de roja temprana**:
```
Si roja en minuto < 30 → impacto alto
  → Excluir resultado del cálculo de forma defensiva [OUTLIER]
  → Advertir: "Resultado afectado por roja temprana — no refleja capacidad real"

Si roja en minuto 30-60 → impacto medio
  → Incluir con peso rebajado (0.5) en forma defensiva
  → Advertir: "Partido con roja a [minuto] min — resultado rebajado"
```

**Bajas por acumulación de amarillas** (relevante en ligas con sanción por 5 amarillas):
```
Si jugador tiene 4+ amarillas y próximo partido es importante:
→ Advertir: "Riesgo de baja por acumulación: [Jugador] con 4 amarillas"
→ Impacto estimado en defensa: [Alto/Medio] si es titular
```

**Correlaciones de tarjetas** (si N>=10):
```
Tarjetas90 vs GC90    → ¿equipo físico concede más goles?       [DER]
Tarjetas90 vs Ranking   → ¿equipos de abajo son más físicos?     [INF-M]
RojaDirecta% vs Puntos → ¿rojas afectan rendimiento competitivo? [INF-M]
```

#### Corners

```
Indicadores de corners por ventana:
- CornersFavor90 = Σ(corners_a_favor) / partidos_jugados    [DER] — si disponible en stats
- CornersContra90 = Σ(corners_en_contra) / partidos_jugados [DER]
- CornerRate = CornersFavor90 + CornersContra90              [DER]
- IC (Índice de Corner) = CornersFavor90 / CornerRate        [DER] — ratio 0-1

Interpretación:
- IC > 0.55 → equipo que genera más corners que recibe (ofensivo)
- IC < 0.45 → equipo que recibe más corners que genera (defensivo)
- CornerRate > 11 → partidos con muchas interrupciones / equipos directos
- CornerRate < 9  → partidos cerrados / posesivos
```

**Correlaciones de corners** (si N>=10):
```
CornersFavor90 vs GF90     → ¿equipo que genera corners crea goles?     [INF-M]
CornersContra90 vs GC90     → ¿equipo que recibe corners concede más?    [INF-M]
CornerRate vs Over25%       → ¿partidos con muchos corners = más goles?  [INF-M]
IC vs GDR                  → ¿equipo con IC alto domina territorialmente? [INF-M]
```

**Perfil de corners por contexto**:
```
Separar en ventanas:
- CornersFavor90 como local vs como visitante
- CornersFavor90 vs Top-10 vs vs Resto
- CornersFavor90 en Champions vs Liga vs Copa
```

**Output de disciplina en tabla**:
```
| Indicador         | Valor  | Tipo | Nota |
|-------------------|--------|------|------|
| Amarillas90       | X.XX   | [DER]|      |
| Rojas90           | X.XX   | [DER]|      |
| TARJ90            | X.XX   | [DER]| [Perfil] |
| IC (corners)      | X.XX   | [DER]| [Ofensivo/Defensivo] |
| CornersFavor90    | X.XX   | [DER]|      |
| CornersContra90   | X.XX   | [DER]|      |

[Perfil]: Disciplina [Alta/Normal/Baja/Muy Baja]
[Ofensivo/Defensivo]: IC = X.XX → equipo [genera más/recibe más] corners
```

**Refs con árbitro**:
```
Usar Get_MatchEvent_Referee_by_Event_ID para identificar al árbitro.
Luego inferir patrón de tarjetas del árbitro:
- Árbitro histórico > 5 amarillas/ppartido → árbitro estricto
- Árbitro histórico < 3 amarillas/ppartido → árbitro laxo
- Ajustar TARJ90 estimado si hay información del árbitro
```

---

## Capa 3 — Detección de Patrones

### 3.1 Identificación de Streaks

Detectar rachas activas en los últimos partidos:

```
Streak Victoria: [X] victorias consecutivas detectadas
Streak Derrota: [X] derrotas consecutivas detectadas
Streak BTS: [X] partidos consecutivos con ambos marcan
Streak CS: [X] partidos consecutivos con clean sheet
Streak Over25: [X] partidos consecutivos con over 2.5
Streak SinCS: [X] partidos consecutivos sin clean sheet
```

**Formato de reporte**:
```
🔥 Rachas detectadas en [EQUIPO]:
- Victoria (3): Últimos 3 partidos ganados
- Over 2.5 (4): 4 de últimos 5 han tenido 3+ goles
- BTTS (3): Ambos marcaron en 3 partidos consecutivos
- ⚠️ Sin CS (2): 2 últimos partidos sin mantener portería a cero
```

### 3.2 Detección de Sesgos de Muestra

**Sesgo por rivales homogéneos**:
```
Si en los últimos 5 partidos el opponent_ranking_avg < 10 (escala 1-20)
→ Advertir: "Forma construida contra rivales débiles — poco representativa"
```

**Sesgo por dependencia de un indicador**:
```
Si un equipo gana 80% de partidos pero:
- 60% de victorias son por 1-0
- 40% de victoria dependen de gol de un solo jugador
→ Advertir: "Alta dependencia de tight scores y/o jugador individual"
```

**Sesgo por local/visitante**:
```
Si home_win% >> away_win% (diferencia > 30%)
→ Advertir: "Fuertes características de equipo local — aplicar descuento fuera"
```

### 3.3 Señales de Inestabilidad

Detectar señales que sugieren rendimiento no sostenible:

```
1. Alta variance en resultados recientes:
   - GF90 oscila mucho entre partidos (ej: 0, 4, 1, 3, 0)
   - Gol promedio a favor y en contra muy variable pero sin patrón claro

2. Clean sheets intermitentes:
   - CS% bajo aunque GC90 bajo
   - Indica porteros que salvan puntos improbables (suerte/stochastic)

3. Over-reliance en última partido:
   - Último partido fue goleada o derrota abultada
   - Puede distorsionar forma si se pondera solo por resultado

4. Lesiones/rotaciones masivas:
   - +3 lesiones de titulares en semana previa
   - Advertir: "Rendimiento puede no reflejar once titular"
```

### 3.4 Patrones de Mercado Tradicional (Informativos — NO Apuestas)

Estos indicadores son PURAMENTE INFORMATIVOS para contextualizar el partido,
no para recomendar mercados:

```
Over 2.5% histórico del equipo en Champions, Liga, Copa
BTTS% histórico del equipo
Primera mitad más productiva que segunda (o viceversa)
Patrón de tarjetas (alta/baja intensidad)
Ritmo de corners (generador alto/bajo)
```

---

## Capa 4 — Correlaciones

### 4.1 Cuándo Calcular Correlaciones

**Regla**: Solo calcular correlaciones si:
- `N >= 10` partidos en la muestra
- Variables numéricas continuas (no categóricas puro)
- Interpretation documentada como "correlación, no causalidad"

### 4.2 Correlaciones Disponibles con Datos de la API

```
CORRELACIONES CALCULABLES (sobre histórico de partidos):

1. GF90 vs Posesión%           → ¿más posesión = más goles?
2. GF90 vs Tiros               → (si disponible en stats del partido)
3. GC90 vs Posesión%           → ¿más posesión = menos gc?
4. Win% vs Home/Away           → ¿local advantage significativo?
5. O25% vs BTTS%               → ¿partidos con muchos goles suelen ser BTS?
6. GDR vs Ranking Oponente      → ¿rendimiento vs equipos mejores/peores?
7. Corners90 vs GF90           → ¿equipo que genera corners crea goles?
8. Tarjetas90 vs GC90          → ¿equipo agresivo concede más?
9. GF90 vs MinPromedioJugClave → ¿rendimiento de crack = ataque mejora?
```

**Formato de reporte**:
```
Correlación detectada: GF90 vs Home/Away
r = +0.42 (N=15) → Correlación moderada positiva
Interpretación: El equipo marca +0.42 goles más por partido en casa que fuera.
Nota: Muestra pequeña (N=15) — correlación marginal, no concluyente.
```

### 4.3 Nivel de Confianza de Correlación

```
N >= 20:        "Correlación robusta"
10 <= N < 20:   "Correlación tentativa — muestra limitada"
5 <= N < 10:    "Tendencia observada — muestra muy pequeña"
N < 5:          NO calcular correlación — informar "muestra insuficiente"
```

---

## Capa 5 — Detección de Outliers

### 5.1 Definición de Outlier en Contexto Fútbolístico

Un resultado se considera outlier si:

```
1. Goles > GF90_global + 2*std(gf90_histórico)
   → Goleada inhabitual (ej: equipo que promedia 1.5 gf90 recibe 5-0)

2. Tarjetas Rojas tempranas (min < 20) afectan resultado desproporcionadamente
   → Excluir del cálculo de forma defensiva

3. Partido con contexto excepcional:
   - Penalizaciones, awards, partidos void
   - Equipos con rotaciones masivas confirmadas
   - Condiciones climáticas extremas documentadas

4.Resultado extremadamente atypico given opponent quality:
   - Equipo weak (ranking > 15) golea a top-3 por > 3 goles
   - Excluir o rebajar peso
```

### 5.2 Manejo de Outliers

```
OPCIÓN A — EXCLUIR:
Si outlier sesga fuertemente (ej: 8-0 vs filial):
→ Excluir partido del cálculo de forma
→ Documentar: "1 partido excluido: [equipo] 8-0 vs [oponente] (fecha) por goleada atípica"

OPCIÓN B — REBAJAR PESO:
Si no es claro que sea inválido pero sí atypico:
→ Aplicar peso de 0.5 en lugar de 1.0 a ese partido
→ Documentar: "1 partido con peso rebajado (0.5): [resultado] por [razón]"

OPCIÓN C — INCLUIR CON NOTA:
Si podría ser real (ej: equipo en racha genuina):
→ Incluir pero documentar: "Incluido con nota: goleada podría indicar cambio táctico"
```

### 5.3 Verificación Post-Outlier

Después de excluir/rebajar outliers, recalcular:
- GF90 y GC90
- Win rate
- Over 2.5 y BTTS rates
- Comparar con y sin outliers y reportar diferencia

```
Ejemplo:
GF90 con outliers: 2.1
GF90 sin outliers: 1.7  (diferencia: -0.4, indica goleadas inflaron media)
→ Advertir al usuario
```

---

## Capa 6 — Probabilidades Estimadas con Confianza

### 6.1 Modelo de Probabilidad

**NO usar heurísticas simples como "equipo local +10%"**.
Construir probabilidad basada en capas de evidencia:

```
PROBABILIDAD_WIN_LOCAL = f(
    forma_global_ponderada,
    forma_local_reciente,
    forma_vs_tipo_rival,
    ventaja_local_estudiada,
    descanso_días,
    lesiones_importantes,
    h2h_reciente,
    contexto_competicion
)
```

**Método de combinación recomendado**:
```
Ponderación bayesiana simplificada:

P_final = (P_forma * peso_forma) + (P_h2h * peso_h2h) + (P_local * peso_local) + (P_confirmado * peso_confirmado)

Donde:
- P_forma = Win% global del equipo en últimos 10 (peso: 0.30)
- P_h2h = Win% en H2H últimos 5 encuentros (peso: 0.25)
- P_local = Win% solo como local (peso: 0.20)
- P_confirmado = indicadores duros (lesiones confirmadas, descanso, etc.) (peso: 0.25)

**Reglas de reducción de peso H2H — OBLIGATORIAS**:

El peso del H2H (0.25) se debe REDUCIR en los siguientes casos:

| Condición | Reducción | Peso Resultante | Razón |
|-----------|-----------|-----------------|--------|
| N_H2H < 3 partidos | peso → 0.05 | 0.05 | Muestra estadísticamente insignificante |
| Todos los H2H > 3 años | peso → 0.05 | 0.05 | Plantillas y DTS completamente distintos |
| Cambio masivo de plantilla (>5 titulares distintos) | peso → 0.10 | 0.10 | El equipo actual no es el mismo que generó el H2H |
| Cambio de DT principal desde último H2H | peso → 0.10 | 0.10 | Sistema de juego y motivación alterados |
| H2H solo en competiciones diferentes (ej: UCL vs pretemporada) | peso → 0.10 | 0.10 | Contexto competitivo no comparable |
| H2H en fase de grupos vs fase eliminatoria | peso → 0.15 | 0.15 | Intensidad y motivación radicalmente distintas |

**Nota sobre H2H**: El head-to-head histórico puede ser engañosamente representativo.
En fútbol, un partido de hace 4 años con una plantilla y DT completamente distintos
aporta muy poca información sobre el resultado actual. SIEMPRE verificar las
condiciones anteriores antes de asignar peso completo al H2H.
```

### 6.2 Niveles de Confianza

Cada predicción incluye su nivel de confianza:

```
CONFIANZA ALTA (85-100%):
- Muestra >= 10 partidos por contexto
- Sin lesiones importantes confirmadas
- Sin outliers significativos
- H2H con muestra >= 5 partidos
→ "Predicción robusta — alta confianza en la estimación"

CONFIANZA MEDIA (60-84%):
- Muestra 5-9 partidos
- 1-2 dudas (lesión posible, descanso, H2H limitado)
- Sin outliers severos
→ "Predicción moderada — ciertos factores incertidumbre"

CONFIANZA BAJA (35-59%):
- Muestra < 5 partidos en contexto evaluado
- Lesiones importantes no confirmadas
- H2H muy antiguo o sin muestra
- Alta varianza en resultados recientes
→ "Predicción tentativa — muestra insuficiente para certeza"

CONFIANZA MUY BAJA (<35%):
- < 3 partidos en ventana
- Múltiples outliers o resultados anomalíos
- Equipos sin histórico en la competición
→ "No es posible generar predicción fiable — datos insuficientes"
```

### 6.3 Estimación de Score Esperado

```
SCORE ESPERADO = (
    (GF90_LOCAL_ponderado + GC90_VISITANTE_ponderado) / 2,
    (GF90_VISITANTE_ponderado + GC90_LOCAL_ponderado) / 2
)

Con intervalo:
- Score más probable = moda de últimos resultados entre estos equipos
- Rango esperado = min(GF90*1.2, GC90*1.2) a max(...)
- Goles totales esperados = (goles_local + goles_visitante) +- 1.5
```

---

## Output Format — Estructura del Análisis

```markdown
# Football Analysis Engine

**Partido**: [EQUIPO LOCAL] vs [EQUIPO VISITANTE]
**Competición**: [NOMBRE] | **Fecha**: [DÍA MES AÑO HORA]
**Venue**: [ESTADIO] ([CIUDAD])

---

## 🔍 Forma Global — [EQUIPO LOCAL]

### Forma Reciente (Ventanas Móviles)

| Ventana | PJ | V | E | D | GF | GC | GF90 | GC90 | GDR | CS% | O25% | BTS% |
|---------|----|---|---|---|----|----|------|------|-----|-----|------|------|
| Últimos 3 | X | X | X | X | XX | XX | X.XX | X.XX | ±X  | XX% | XX%  | XX%  |
| Últimos 5 | X | X | X | X | XX | XX | X.XX | X.XX | ±X  | XX% | XX%  | XX%  |
| Últimos 10 | X | X | X | X | XX | XX | X.XX | X.XX | ±X  | XX% | XX%  | XX%  |

### Forma por Competición

| Competición | PJ | V | E | D | GF | GC | Win% | Nota |
|-------------|----|---|---|---|----|----|------|------|
| [Liga]     | XX | X | X | X | XX | XX | XX%  |       |
| [Copa]     | X  | X | X | X | XX | XX | XX%  |       |
| [UCL/...]  | XX | X | X | X | XX | XX | XX%  |       |
| **Global** | XX | X | X | X | XX | XX | XX%  | Ponderado |

### Forma Local vs Visitante

| Contexto | PJ | V | E | D | GF90 | GC90 | Win% |
|----------|----|---|---|---|------|------|------|
| Como Local  | XX | X | X | X | X.XX | X.XX | XX% |
| Como Visitante | XX | X | X | X | X.XX | X.XX | XX% |
| vs Top-10   | XX | X | X | X | X.XX | X.XX | XX% |

### Rachas Activas Detectadas
- 🔥 **Victoria (X)**: [detalle]
- 🔥 **Over 2.5 (X)**: [detalle]
- ⚠️ **Sin CS (X)**: [detalle]
- ⚠️ **Derrota (X)**: [detalle]

### Jugadores Clave — Forma Global

| Jugador | Pos | G | A | Min% | G90  | A90  | Ritmo | Nota |
|---------|-----|---|---|------|------|------|-------|------|
| [JC1]   | DEL | XX| XX| XX%  | X.XX | X.XX | 🔥 Alto |       |
| [JC2]   | MED | XX| XX| XX%  | X.XX | X.XX | ✅ Medio |      |
| [JC3]   | POR | - | - | XX   | -    | -    | ✅ Normal |    |

### Lesiones y Bajas Confirmadas
- ❌ **[Jugador]**: [Lesión] (desde [fecha]) — impact: [Alto/Medio/Bajo]
- ⚠️  **[Jugador]**: Duda — entrenamiento aparte — impact: [Alto/Medio/Bajo]

### Contexto Adicional
- Descanso desde último partido: **X días** (ideal: 7+, aceptable: 5+, ajustado: <5)
- Derby / Partido grande: **Sí/No**
- Motivación: **[Descripción]**
- Importancia competitiva: **[Descripción]**

---

## 🔍 Forma Global — [EQUIPO VISITANTE]

[Repetir misma estructura que equipo local]

---

## 📊 Head-to-Head ([LOCAL] vs [VISITANTE])

### Historial Completo

| Fecha | Competición | Marcador | Nota |
|-------|-------------|----------|------|
| [Fecha] | [Comp] | X - X | [Nota] |
| [Fecha] | [Comp] | X - X | [Nota] |
| [Fecha] | [Comp] | X - X | [Nota] |

### Resumen H2H
- Victorias [LOCAL]: X
- Victorias [VISITANTE]: X
- Empates: X
- En [ESTADIO]: [LOCAL] X-X-[VISITANTE]
- Over 2.5: X/X (XX%)
- BTS: X/X (XX%)
- Media goles: X.XX por partido

---

## 📈 Predicción Cuantitativa

### Estimación de Score

```
[EQUIPO LOCAL]: X.X-X.X [EQUIPO VISITANTE]
Rango estimado: [X-X] a [X-X] goles totales
Intervalo de confianza: 80% → [X,X] - [X,X]
```

### Probabilidades Estimadas

| Resultado | Probabilidad | Confianza | Método |
|-----------|-------------|-----------|--------|
| Victoria [LOCAL] | XX% | [ALTA/MED/Baja] | Ponderación múltiple |
| Empate | XX% | [ALTA/MED/Baja] | Ponderación múltiple |
| Victoria [VISITANTE] | XX% | [ALTA/MED/Baja] | Ponderación múltiple |

### Over/Under Estimado

| Mercado | Frecuencia Hist. | Estimación | Confianza |
|---------|-----------------|------------|-----------|
| Over 2.5 | XX% (N=XX) | XX% | [ALTA/MED/Baja] |
| BTS Sí | XX% (N=XX) | XX% | [ALTA/MED/Baja] |
| Over 3.5 | XX% (N=XX) | XX% | [ALTA/MED/Baja] |

---

## 🧠 Statistical Insights

### Tamaño de Muestra

| Contexto | N | Validez |
|----------|---|---------|
| Forma global [LOCAL] | XX partidos | ✅ Robusta / ⚠️ Limitada / ❌ Insuficiente |
| Forma global [VISITANTE] | XX partidos | ✅ Robusta / ⚠️ Limitada / ❌ Insuficiente |
| H2H reciente | XX partidos | ✅ Robusta / ⚠️ Limitada / ❌ Insuficiente |
| Forma local [LOCAL] | XX partidos | ✅ Robusta / ⚠️ Limitada / ❌ Insuficiente |
| H2H en [ESTADIO] | XX partidos | ✅ Robusta / ⚠️ Limitada / ❌ Insuficiente |

### Correlaciones Detectadas (Modo Profundo — si N>=10)

| Variables | r | N | Interpretación | Confianza |
|-----------|---|---|----------------|-----------|
| GF90 vs Local | +0.XX | XX | [Texto] | [Alta/Tentativa] |
| Win% vs Ranking | +0.XX | XX | [Texto] | [Alta/Tentativa] |
| O25% vs BTS% | +0.XX | XX | [Texto] | [Alta/Tentativa] |

**Si N < 10 en todos los contextos**: "Correlaciones no calculables — muestra insuficiente (N<10 por contexto)."

### Patrones Recientes Identificados

```
[EQUIPO LOCAL]:
- [Patrón 1]: [Descripción] — Confianza: [Alta/Media]
- [Patrón 2]: [Descripción] — Confianza: [Alta/Media]
- ⚠️ Sesgo detectado: [Descripción] — Ver nota

[EQUIPO VISITANTE]:
- [Patrón 1]: [Descripción] — Confianza: [Alta/Media]
- [Patrón 2]: [Descripción] — Confianza: [Alta/Media]
- ⚠️ Sesgo detectado: [Descripción] — Ver nota
```

### Outliers Identificados y Manejados

```
OUTLIERS EXCLUIDOS:
- [Partido]: [Resultado] — Razón: [Goleada inhabitual / roja temprana / contexto excepcional]
- Impacto en GF90: [-X.XX] — Recalculado sin este resultado

OUTLIERS CON PESO REBAJADO:
- [Partido]: [Resultado] — Razón: [Posible anormal pero no concluyente] — Peso: 0.5

PARTIDOS INCLUIDOS CON NOTA:
- [Partido]: [Resultado] — Nota: [Podría indicar cambio táctico / racha real]
```

### Estabilidad de la Predicción

```
Nivel de confianza general: [ALTA / MEDIA / BAJA / MUY BAJA]

Factores que reducen confianza:
- ❌ Muestra H2H insuficiente (N=X < 5)
- ⚠️ Lesiones no confirmadas en [Jugador]
- ⚠️ Alta varianza en últimos resultados (std GF90 = X.XX)
- ⚠️ Sesgo por rivales homogéneos en ventana reciente

Factores que aumentan confianza:
- ✅ Muestra robusta en todos los contextos (N>=10)
- ✅ Sin lesiones importantes en eleven titular
- ✅ Descanso adecuado (X días)
- ✅ H2H con patrón consistente
```

### Señales de Alerta

```
⚠️ [SEÑAL]: [Descripción] — Puede afectar: [Predicción / Confianza / Score]
⚠️ [SEÑAL]: [Descripción] — Puede afectar: [Predicción / Confianza / Score]

Si no hay señales: "Sin alertas significativas — datos consistentes."
```

### Resumen Descriptivo

```
[EQUIPO LOCAL] llega con [describir forma: ej: "racha de 3 victorias,
media de 2.1 goles por partido, pero sin clean sheet en 2 partidos fuera"].
[EQUIPO VISITANTE] llega con [describir forma análoga].

El contexto de [LOCAL/ESTADIO/COMPETICIÓN] sugiere [describir ventaja o igualdad].
El H2H en [ESTADIO] muestra [describir patrón].

PREDICCIÓN PRINCIPAL: [Descriptor cualitativo — ej: "Partido equilibrado con ligera ventaja local,
se esperan 2-3 goles, ambos equipos con capacidad de marcar."]
NIVEL DE CONFIANZA: [XX%] — [Razón breve]
```

---

## Recommendations — Módulo de Recomendaciones

### Nota sobre honestidad epistemológica

Este módulo traduce todo el análisis previo en recomendaciones accionables.
La regla fundamental es:

**No fabricar precisión que no existe.**

Esto significa:
- Nunca inventar porcentajes. Si el dato no existe, decir "[N/A]".
- Usar rangos, no valores puntuales.
- Ajustes cualitativos (fuerte/moderado/débil), no "+8%".
- Distinguir explícitamente entre lo que los datos muestran y lo que se infiere.
- Expresar siempre la confianza con su razón.

---

### 1. Recomendaciones de Partido

#### 1.1 Cómo construir cada recomendación

Cada recomendación sigue este formato:

```
NOMBRE_EVENTO
Rango: [MIN-MAX]%
Confianza: [ALTA / MEDIA / BAJA]
Base: [qué dato [API/DER] sustenta esto]
Señales a favor: [lista de señales positivas — cada una con tipo de dato]
Señales en contra: [lista de señales negativas — cada una con tipo de dato]
Nota: [si hay sesgo, muestra pequeña, outlier, o factor que no podemos evaluar]
```

**Regla de señales**: Cada señal se expresa como descriptor cualitativo, no como ajuste numérico:

| Descriptor | Significado |
|-----------|-------------|
| Señal fuerte a favor | Dato [DER] consistente con más de 3 indicadores |
| Señal moderada a favor | Dato [DER] o [INF-M] con soporte moderado |
| Señal débil a favor | Solo [INF-M] o con N pequeña |
| Señal moderada en contra | Dato [INF-M] o [DER] con signo negativo |
| Señal débil en contra | Solo [INF-B] o muestra muy pequeña |

**Regla de cap de certeza**: Ninguna predicción para un evento deportivo debe declararse con confianza ALTA si se apoya en ajustes [INF-M] o [INF-B]. La confianza ALTA requiere que la base sea [DER] en más del 80% de los componentes.

#### 1.2 Goles Totales

**Over 2.5 Goles**
```
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: Promedio de O25% de ambos equipos en últimos 10 partidos [DER]
  - [EQUIPO LOCAL] O25%: XX% (N=X) [DER]
  - [EQUIPO VISITANTE] O25%: XX% (N=X) [DER]
  - Base combinada: (XX% + XX%) / 2 = XX% [DER]

Señales a favor:
  • Ambos con GF90 > 1.5 [DER]
  • BTTS% combinado > 55% en últimos 5 [DER]
  • GC90 de ambos > 1.0 [DER]
  • H2H con O25% > 60% [DER]

Señales en contra:
  • Partido de alta importancia (fase eliminatoria) — tiende a ser más prudente [INF-M]
  • Descanso < 4 días para alguno — posible fatiga [INF-M]
  • Algún equipo con CS% local > 60% y ataque del otro débil [DER]

Nota: [ej: "H2H muy antiguo (2018) — plantillas y DT distintos. No usar como señal fuerte."]
```

**Over 1.5 Goles**
```
Similar estructura. Base: O15% combinado de ambos [DER].
Señales standard: ambos con GF90 > 1.2, BTTS presente, etc.
```

**Over 3.5 Goles**
```
Similar estructura. Base: max(O35_local, O35_visitor) × 0.7 [DER — estimador conservador].
Usar solo si base > 35%. Marcar como [INF-M] por ser estimador conservador.
Señales a favor: GC90 combinados > 1.5, H2H O35% > 50%.
```

#### 1.3 Ambos Equipos Marcan (BTTS)

```
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: BTTS% combinado de ambos en últimos 10 partidos [DER]
  - [LOCAL] BTTS% como local: XX% (N=X) [DER]
  - [VISITANTE] BTTS% como visitante: XX% (N=X) [DER]

Señales a favor:
  • GC90_local > 1.2 Y GF90_visitante > 1.2 [DER]
  • BTTS% H2H en últimos 5 > 60% [DER]
  • Ambos con alta producción ofensiva (GF90 > 1.5) [DER]

Señales en contra:
  • Algún equipo con CS% > 55% y ataque débil del rival [DER]
  • Lesión de delantero titular en alguno [INF-M]
  • Descanso < 4 días — fatiga puede reducir ambición ofensiva [INF-M]
```

#### 1.4 Clean Sheet

```
Clean Sheet Local:
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: CS% del equipo local en últimos 10 partidos como local [DER]

Señales a favor:
  • GC90_visitante < 1.0 [DER]
  • Ataque visitante débil (GF90 < 1.0) [DER]
  • Portero sin lesiones y ritmo > 85% [DER]

Señales en contra:
  • GC90_local > 1.3 [DER]
  • GF90_visitante > 1.5 [DER]
  • Portero en forma baja (últimos 3: >1.5 GC por partido) [DER]
```

#### 1.5 Resultado 1X2

```
Victoria Local:
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: Win% ponderado del equipo local en últimos 10 (Capa 6) [DER]

Señales a favor:
  • Forma global buena (Win% > 55% en últimos 10) [DER]
  • Descanso local > 7 días vs visitante < 4 [INF-M]
  • Lesión de clave jugador visitante confirmada [INF-M]
  • H2H favorable en [ESTADIO] con N >= 5 [DER]

Señales en contra:
  • Forma débil local (Win% < 40%) [DER]
  • Descanso local < 3 días [INF-M]
  • H2Hweight reducido por cambios de plantilla (aplicar regla H2H)
  • Derby / presión alta en visitante [INF-M]

Empate:
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: Draw% histórico de ambos en últimos 10 [DER]

Señales a favor:
  • Ambos con forma inestable (alta std en resultados) [DER]
  • H2H con múltiples empates (> 2 en últimos 5) [DER]
  • Partidos evenly matched en papel (forma similar, ranking cercano) [DER]

Victoria Visitante: estructura análoga.
```

#### 1.6 Corners

```
Over Corners 10.5:
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: (CornersFavor90_local + CornersFavor90_visitante + CornersContra90_local + CornersContra90_visitante) / 2 [DER]

Señales a favor:
  • IC de ambos > 0.52 (generan más de los que reciben) [DER]
  • CornerRate combinado > 10.5 en últimos 5 [DER]
  • Equipos con estilo directo (más possessions finalizadas en corner) [INF-M]

Señales en contra:
  • IC de alguno < 0.43 (equipo muy defensivo) [DER]
  • Partido de baja intensidad (posesión larga, poco vertical) [INF-M]
  • Descanso < 4 días para ambos — posible juego controlado [INF-M]

[Si CornersFavor90 no disponible de la API: marcar como [N/A]
y indicar: "Datos de corners no disponibles en API para este contexto."]
```

#### 1.7 Tarjetas

```
Over Tarjetas 5.5:
Rango: [BASE_MIN-BASE_MAX]%
Confianza: [ALTA / MEDIA / BAJA]

Base: (TARJ90_local + TARJ90_visitante) / 2 × 2 [DER]

Señales a favor:
  • TARJ90 combinado > 4.5 [DER]
  • Partido de alta intensidad (rival directo, alta presión) [INF-M]
  • Árbitro estricto (histórico > 4.5 amarillas por partido) [INF-M]
  • Descanso < 4 días para ambos [INF-M]

Señales en contra:
  • TARJ90 combinado < 3.0 [DER]
  • Árbitro laxo (histórico < 3 amarillas por partido) [INF-M]
  • Equipos con disciplina alta (IC > 0.55) y sin persecucion intensidad [INF-M]

Nota sobre árbitro: Si no se dispone del histórico del árbitro,
marcar como [INF-M] y no usar como señal fuerte.
```

#### 1.8 Tabla Resumen de Recomendaciones

```
### Match Recommendations

| Evento              | Rango         | Confianza | Señales a favor (principales)             | Fuente principal |
|---------------------|---------------|-----------|--------------------------------------------|-----------------|
| Over 1.5 goles     | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| Over 2.5 goles     | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| Over 3.5 goles     | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER/INF-M]     |
| BTTS — Sí          | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| CS Local            | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| CS Visitante        | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| Victoria Local (1)  | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| Empate (X)          | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| Victoria Visitante(2)| XX-XX%       | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER]           |
| Over Corners 10.5   | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER/INF-M]     |
| Over Tarjetas 5.5   | XX-XX%        | [A/M/B]   | [Hasta 3 señales + tipo dato]             | [DER/INF-M]     |
```

---

### 2. Recomendaciones de Jugadores

#### 2.1 Estructura

Para 2-3 jugadores clave por equipo:

```
[JUGADOR] — [EQUIPO]
Rol en el partido: [delantero/goleador/creador]

Gol del jugador:
  Rango: [BASE_MIN-BASE_MAX]%
  Confianza: [ALTA / MEDIA / BAJA]
  Base: G90 del jugador × 100 [DER] + contexto [INF-M]
  Minutos ritmo: XX% (X/X partidos con 90 min) [DER]
  Forma reciente: [X goles en últimos X partidos] [DER]
  A favor: [hasta 2 señales positivas]
  En contra: [hasta 2 señales negativas]
  Nota: [si viene de lesión, rotación esperada, o dato incompleto]
```

#### 2.2 Asistencia

```
Asistencia del jugador:
  Rango: [BASE_MIN-BASE_MAX]%
  Confianza: [ALTA / MEDIA / BAJA]
  Base: A90 del jugador × 100 [DER]
  A favor: [ hasta 2 señales]
  En contra: [ hasta 2 señales]
```

#### 2.3 Tabla Resumen Jugadores

```
### Player Recommendations

| Jugador          | Equipo    | Gol rango | Conf | Asistencia rango | Conf | Nota                      |
|-----------------|-----------|-----------|------|-----------------|------|---------------------------|
| [Jugador 1]     | [LOCAL]   | XX-XX%    | [A/M/B] | XX-XX%         | [A/M/B] | [ej: lesionado, forma alta] |
| [Jugador 2]     | [LOCAL]   | XX-XX%    | [A/M/B] | XX-XX%         | [A/M/B] | [ej: maxima amenaza]        |
| [Jugador 3]     | [VISIT.]  | XX-XX%    | [A/M/B] | XX-XX%         | [A/M/B] | [ej: visitante, rotation]   |
```

---

### 3. Matriz de Incertidumbre

Esta tabla cruza tamaño de muestra y tipo de dato para determinar la confianza
de cada rango estimado. Usarla para calibrar cada recomendación.

```
| Muestra N | Base [DER] | Base [INF-M] | Base [INF-B] |
|-----------|-----------|--------------|--------------|
| N >= 10   | ALTA      | MEDIA        | BAJA          |
| 5 <= N < 10| MEDIA    | MEDIA        | MUY BAJA      |
| 2 <= N < 5 | BAJA    | MUY BAJA    | NO GENERAR    |
| N < 2     | MUY BAJA  | NO GENERAR  | NO GENERAR    |

Intervalos de confianza por nivel:
- ALTA:    rango ±8 puntos (ej: 65% → 57-73%)
- MEDIA:   rango ±15 puntos (ej: 65% → 50-80%)
- BAJA:    rango ±25 puntos (ej: 65% → 40-90%)
- MUY BAJA: no generar rango numérico, solo descriptor cualitativo

Regla de cumulacion: si 2+ ajustes usan [INF-M], bajar la confianza un nivel.
Regla de H2H: si la recomendación depende de H2H con peso reducido,
la confianza máxima posible es MEDIA aunque la base sea [DER].
```

---

### 4. Síntesis para Toma de Decisiones

Esta sección condensa todo lo anterior en un formato de decisión clara.

```
### Decision Summary

LECTURA:
- Rangos: el número real más probable está dentro del rango.
- Confianza ALTA: el rango es fiable. La mayoria de casos caerán ahí.
- Confianza MEDIA: el rango es orientativo. Casos reales pueden estar fuera.
- Confianza BAJA: el rango es tentativo. Fuera del rango es equally probable.
- Confianza MUY BAJA: no hay suficiente información para un rango fiable.

ACCIONABILIDAD POR NIVEL DE CONFIANZA:

[ALTA] → Recomendación accionable:
  "Over 2.5: 58-72% [ALTA]"
  → rango suficientemente estrecho para uso en análisis o decisión.

[MEDIA] → Recomendación usable con cautela:
  "Over 2.5: 50-80% [MEDIA]"
  → rango amplio pero orientativo. Útil para context, no para decisión directa.

[BAJA] → Solo para context:
  "Over 2.5: 35-85% [BAJA]"
  → rango demasiado amplio. Solo sirve para descartar eventos muy improbables.

[MUY BAJA] → Desestimar para decisión:
  "Over 2.5: [N/A] — datos insuficientes"
  → No incluir en análisis cuantitativo. Solo en nota cualitativa si es relevante.

ELEMENTOS MAS ACCIONABLES (prioridad):
1. Eventos con confianza ALTA y rango estrecho (ancho < 20 puntos)
2. Eventos donde las señales a favor son [DER] en su mayoría
3. Eventos donde el rango no cruza el 50% claramente

ELEMENTOS MENOS ACCIONABLES:
1. Eventos con confianza BAJA o MUY BAJA
2. Rangos que cruzan 50% (ej: 40-75%)
3. Recomendaciones con 2+ señales [INF-B]
```

---

### 5. Ejemplo de Recomendación Honesta

```
Over 2.5 Goles
Rango: 58-72%
Confianza: MEDIA

Base: O25% combinado = (68% + 55%) / 2 = 61.5% [DER]
  — [LOCAL] O25%: 68% en últimos 10 (N=10) [DER]
  — [VISITANTE] O25%: 55% en últimos 10 (N=10) [DER]

Señales a favor:
  • GF90 combinado = 3.6 (> 1.8 de media) [DER]
  • GC90 combinado = 2.3 (> 1.0) [DER]
  • BTTS H2H = 70% en últimos 5 (> 60%) [DER]
  • Ambos con forma ofensiva consistente en últimos 5 [DER]

Señales en contra:
  • Partido de semifinales — alta importância -> più cauto [INF-M]
  • Descanso local solo 3 días [INF-M]

Intervalo: 61.5% ± 15% → 46.5-76.5% → ajustado a 58-72% por sesgo alza
Rango final: 58-72% [MEDIA]

Interpretación: los datos sugieren que el Over 2.5 es el escenario más probable,
con ligera favorabilidad. Sin embargo, el partido de alta importancia introduce
prudencia y el descanso insuficiente del local puede reducir la producción ofensiva.
El rango 58-72% es orientativo — el resultado real más probable está en ese
intervalo, pero un 28-42% de posibilidades están fuera.
No hay certeza. Solo favorabilidad estadisticamente significativa.
```

---

### 6. Integración del Módulo

```
ORDEN DE SECCIONES EN OUTPUT:

1. Forma Global — [EQUIPO LOCAL]
   (incluye sección 2.5 Disciplina y Corners)
2. Forma Global — [EQUIPO VISITANTE]
   (incluye sección 2.5 Disciplina y Corners)
3. Head-to-Head
4. Predicción Cuantitativa
5. Statistical Insights
6. Recommendations ← este módulo (antes llamado Probabilistic Outcomes)
7. Guía Rápida — Reutilización de Datos
8. Principios de la Skill

REGLAS DE REUTILIZACIÓN:
- NO hacer nuevas llamadas API para este módulo
- Todos los inputs ya fueron calculados en Capas 1-6
- Si un dato no está disponible: marcar [N/A] y no forzar rango
- Para partido futuro: usar CornersFavor90 de histórico, no de partido futuro
- Si falta más del 30% de los datos para construir una recomendación:
  → marcar como [N/A] + confianza MUY BAJA
```

---

### 7. Qué NO puede hacer este módulo

```
1. PREDECIR EVENTOS RAROS CON CERTEZA:
   El fútbol tiene varianza inherente alta. Un evento con 80% de probabilidad
   falla 1 de cada 5 veces. Eso no es un error del modelo — es la realidad.

2. CAPTURAR LO TÁCTICO:
   No puede saber si un DT va a cambiar sistema, si un equipo va a presionar alto,
   o si hay duelo táctico especifico que anule al otro. Estas cosas desplazan
   resultados significativamente y no están en los datos.

3. INFERIR xG REAL:
   La API no provee xG. Nosotros usamos proxies (GF90, GC90, distancia de tiro,
   tipo de asistencia). Son útiles pero no son xG. Marcar siempre como [INF-M].

4. SUSTITUIR JUICIO TÁCTICO:
   Los mejores análisis de fútbol combinan datos con entendimiento táctico.
   Este módulo es la capa de datos. La capa táctica sigue siendo responsabilidad
   del usuario que conoce el partido.

5. ELIMINAR LA INCERTIDUMBRE:
   El fútbol es predecible solo parcialmente. Esta skill reduce la incertidumbre
   pero no la elimina. Aceptar que los rangos son rangos, no certezas.
```

## Guía Rápida — Reutilización de Datos

**Principios de eficiencia**:

1. **Los datos de Get_MatchEvent_All_Stats_by_Event_ID alimentan múltiples cálculos**:
   - GF90, GC90 → van a EDA y predicción
   - BTS → va a predicción over/under
   - CS → va a EDA y predicción
   - Corners, tarjetas → van a EDA y correlaciones

2. **Get_Head_to_Head_by_Event_ID alimenta**:
   - H2H Win%
   - H2H Over 2.5
   - H2H BTS
   - H2H Score más común
   - H2H Goles promedio

3. **Get_Standing_All_by_League_ID alimenta**:
   - Ranking actual
   - Home win% / Away win%
   - Goles dentro/fuera
   - vs Top-10 performance

4. **Get_Top_Players_by_Goals + Get_Players_List_All_by_Team_ID alimentan**:
   - Forma global de cada jugador
   - G90 / A90
   - Ritmo de minutos
   - Lesiones/bajas

**Reutilizar, no reconsultar**: Si ya tienes los datos en memoria/respuesta previa,
usarlos para todos los cálculos posibles antes de hacer nuevas llamadas.

---

## Principios de la Skill

1. **Global antes de específico**: Nunca analizar un equipo solo por su liga.
   Cruzar siempre liga + copa + Europa antes de generar conclusiones.

2. **Datos, no opinión**: Toda afirmación debe estar respaldada por datos.
   Si no hay datos, usar "estimado según tendencia" y especificarlo.

3. **Confianza explícita**: Toda predicción incluye su nivel de confianza.
   No exaggerar certeza cuando la muestra es pequeña.

4. **Rate limiting es sagrado**: Si se acerca al límite de 1000/hora,
   priorizar llamadas y avisar al usuario que hay límite.

5. **Outliers documentados**: Resultados atypicos se excluyen, rebajan de peso
   o incluyen con nota — siempre documentados.

6. **Correlaciones cautelosas**: Solo calcular con N>=10.
   Siempre indicar "correlación, no causalidad".

7. **Métricas inferidas explícitas**: Cuando una métrica se infiere y no
   viene directamente de la API, marcar como [INFERIDO].

8. **Predicción descriptiva, no prescriptiva**: El output dice "el equipo
   marca de media 2.1 goles fuera" — NO "apuesta al Over 2.5".

9. **Salida estructurada siempre**: El formato de salida es idéntico
   en todos los análisis para comparabilidad.

10. **Modo rápido vs profundo**: El usuario elige. No forzar modo profundo
    si solo pidió "un análisis rápido del partido de mañana".

---

## Guardado de datos
Guarda porfa ese análisis en un txt en ./claude/skills/football-betting-analysis/football-analysis. Crea una carpeta cuyo nombre corresponda con el nombre de la competición, por ejemplo, Champions League 25-26. Guarda el archivo como EQUIPOLOCAL_EQUIPOVISITANTE_DD_MM_AAAA(JORNADA_X).txt donde X en (JORNADA_X) es el # de la jornada que se juega o si es 1/4 de final u 1/8 lo que corresponda