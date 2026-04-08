# Documento técnico de la skill Football Analysis Engine

Guía completa para reconstruir la skill desde cero y migrarla a otra API

## Qué cubre este documento

- Principios invariantes de la skill, independientemente de la API.
- Flujo completo: parsing, discovery, ingesta, 8 capas, confianza y salida.
- Cómo agregar módulos opcionales como corners, tarjetas, lesionados o tiros a puerta sin romper la lógica base.
- Cómo rehacer la skill sobre una API nueva sin introducir alucinaciones ni pseudo-precisión.

## 1. Propósito y filosofía

La skill está diseñada para producir análisis pre-partido de fútbol en lenguaje probabilístico, no picks categóricos. Su función no es adivinar el resultado, sino organizar evidencia, separar señal de ruido y devolver una lectura clara de qué viene pasando, por qué podría estar pasando, qué podría pasar y qué señales pesan más.

Su arquitectura conceptual debe sobrevivir aunque cambie la API. Por eso la skill no debe depender mentalmente de endpoints concretos, sino de clases de información: contexto del partido, mercado, predicción ML, forma reciente, protagonistas, y señales opcionales enriquecedoras.

La prioridad siempre es confiabilidad operativa. Una skill más corta y disciplinada es preferible a una skill más ambiciosa pero llena de inferencias débiles.

## 2. Invariantes que no deben romperse

- Solo analizar partidos pre-partido. Si el partido ya está en juego o terminó, la skill debe detenerse.
- Toda salida debe estar organizada en 8 capas, aunque alguna capa aparezca degradada.
- Nunca inventar datos que la API activa no provee de forma estructurada o verificable.
- Nunca reemplazar un modelo ML oficial con uno heurístico oculto.
- Siempre expresar incertidumbre y confianza. Nunca vender certeza.
- Toda señal opcional faltante debe marcarse como N/A y quedar fuera del núcleo inferencial.

## 3. Modelo desacoplado de API

La skill debe pensarse en dos capas separadas:

| Nivel | Rol |
|---|---|
| Capa conceptual | Define qué necesita saber el agente: partido, mercado, ML, forma, protagonistas, señales opcionales, confianza y output. |
| Capa de adaptación | Mapea esos requisitos a la API concreta. Si la API cambia, se reemplaza esta capa sin romper la lógica del análisis. |

## 4. Entradas lógicas que la skill necesita

### Obligatorias

Identidad del partido, fecha/rango, equipos involucrados y al menos uno entre odds o predicción ML.

### Muy valiosas

Forma reciente, H2H, xG reciente, player-stats del evento o del contexto equivalente.

### Opcionales enriquecedoras

Corners, tarjetas, lesionados, sancionados, tiros a puerta, posesión, faltas, árbitro, alineaciones probables.

### Meta-reglas

Si una señal opcional no existe en la API activa, la skill debe marcarla como [N/A] y no usarla como base fuerte.

## 5. Flujo operacional completo

**Paso 1 — Parsing NL**  
Resolver equipos, fecha/rango y competición desde lenguaje natural. Normalizar aliases, quitar acentos y detectar ambigüedad.

**Paso 2 — Match discovery**  
Buscar candidatos, priorizar por liga y fecha, y pedir aclaración si hay múltiples partidos plausibles.

**Paso 3 — Data gathering**  
Levantar evento, odds, predicción ML y señales opcionales disponibles. Cada fallo debe traducirse en degradación explícita.

**Paso 4 — Construcción de capas**  
Ejecutar las 8 capas en orden lógico, reutilizando datos previos.

**Paso 5 — Política de confianza**  
Ajustar la confianza por cobertura, coherencia y calidad de muestra.

**Paso 6 — Output final**  
Entregar un informe estructurado, con etiquetas de fuente y lenguaje probabilístico.

## 6. Explicación detallada de las 8 capas

### Capa 1 — Contexto base

**Objetivo:** fijar el marco del partido.  
**Inputs mínimos:** evento, odds y/o ML.  
**Debe producir:** quién juega, cuándo, dónde, qué dice el mercado, qué dice el modelo, si coinciden o chocan.  
Si faltan odds o ML, la capa sigue viva pero parcial.

### Capa 2 — Descriptiva de equipos

**Objetivo:** resumir cómo llegan ambos equipos.  
**Inputs ideales:** forma reciente, goles, xG, over/under, BTTS, rendimiento local/visita, H2H.  
Puede enriquecerse con corners, tarjetas, tiros a puerta o posesión si existen.  
Si estos datos opcionales no están disponibles, se omiten sin afectar la existencia de la capa.

### Capa 3 — Descriptiva de protagonistas

**Objetivo:** medir el peso real de jugadores y disponibilidad competitiva.  
**Inputs ideales:** player-stats, roles, aportes ofensivos/defensivos, riesgo disciplinario.  
Si la API ofrece lesionados o sancionados estructurados, se integran aquí como disponibilidad.  
Si no existe esa cobertura, la capa no debe inventar ausencias: marca [N/A] y sigue.

### Capa 4 — Indicadores compuestos

**Objetivo:** convertir datos sueltos en señales analíticas.  
**Ejemplos:** ventaja ofensiva, fragilidad defensiva, gap de forma, riesgo de over, riesgo de BTTS, coherencia mercado-modelo.  
Aquí también entran indicadores opcionales como índice disciplinario, presión por tiros a puerta o perfil de corners, solo si los datos base existen.  
Si un indicador requiere un dato faltante, el indicador no se calcula.

### Capa 5 — Diagnóstica

**Objetivo:** explicar por qué una tendencia puede ser real o engañosa.  
Debe distinguir entre volumen real, caos defensivo, sobre-rendimiento, sub-rendimiento y contradicciones.  
Las señales opcionales solo aparecen como soporte si están disponibles.  
Sin datos de soporte, la capa debe reducir afirmaciones y usar lenguaje cauteloso.

### Capa 6 — Ponderación de señales

**Objetivo:** jerarquizar qué pesa fuerte, moderado, débil o no utilizable.  
Las señales opcionales nunca pueden escalar a “fuertes” si la fuente es incompleta o indirecta.  
La ausencia de corners, tarjetas o lesionados no invalida la capa; solo reduce profundidad.  
Esta capa impide que el agente trate como decisivo un dato débil.

### Capa 7 — Predictiva

**Objetivo:** transformar la evidencia en escenarios probables.  
Las probabilidades 1X2 y de goles deben venir de ML y/o odds. Los indicadores modulan soporte y confianza, no reemplazan la base probabilística.  
Corners, tarjetas o bajas pueden matizar el tipo de partido o la confianza, pero no deben generar probabilidades numéricas por sí solos.  
Sin odds ni ML no se emiten probabilidades numéricas fuertes.

### Capa 8 — Prescriptiva ligera

**Objetivo:** decir qué lecturas tienen mejor soporte.  
Debe listar señales fuertes, alertas y mercados/lecturas con mejor o peor sustento.  
Si corners, tarjetas o lesionados no estaban disponibles, eso debe figurar como limitación y no como señal omitida silenciosamente.  
Nunca debe sonar como certeza ni como recomendación ciega.

## 7. Cómo integrar corners, tarjetas, lesionados y otras señales opcionales

Estas señales deben modelarse como módulos enriquecedores, no como requisitos mínimos. La regla general es simple: si la API activa las provee de forma estructurada y verificable, se integran; si no, se marcan como [N/A] y no afectan la inferencia principal.

| Señal opcional | Dónde entra | Qué puede aportar | Qué hacer si falta |
|---|---|---|---|
| Corners | Capas 2, 4, 5 y 8 | Ritmo de partido, presión territorial, soporte para lecturas de volumen ofensivo. | Marcar [N/A]. No inferir corners fuertes ni usarlos como fundamento central. |
| Tarjetas | Capas 2, 3, 4, 5 y 8 | Perfil disciplinario, riesgo de partido friccionado, alertas por expulsiones o sanciones. | Marcar [N/A]. No construir lectura disciplinaria fuerte. |
| Lesionados / bajas | Capas 3, 5 y 8 | Disponibilidad real, pérdida de peso ofensivo o defensivo, contexto competitivo. | Marcar [N/A]. No asumir ausencias ni dudas. |
| Tiros a puerta | Capas 2, 4 y 5 | Calidad de volumen ofensivo, soporte para goles esperados y producción real. | Marcar [N/A]. No usarlos como soporte principal si no existen. |
| Posesión / faltas / árbitro | Capas 2, 4, 5 y 8 | Contexto de estilo, fricción, interpretación secundaria. | Usarlos solo como contexto. Si faltan, no inventar proxies fuertes. |

### Regla operativa clave

Ninguna de estas señales opcionales puede convertirse en condición obligatoria del análisis. Su ausencia solo reduce riqueza descriptiva y capacidad explicativa; no debe bloquear la skill mientras existan evento y base probabilística suficiente.

## 8. Política de confianza

| Cobertura | Confianza máxima sugerida | Comentario |
|---|---|---|
| Evento + odds + ML + forma suficiente | Alta | El sistema puede emitir lectura fuerte, siempre en lenguaje probabilístico. |
| Evento + odds + ML, pero sin forma o player-stats | Media-alta | Buena base predictiva, explicación menos profunda. |
| Evento + odds o evento + ML | Media | Puede haber lectura útil, pero con límites claros. |
| Evento solo | Baja | Solo contexto; no debe vender escenarios fuertes. |
| Datos opcionales faltantes | No bajan por sí solos la confianza global | Solo reducen profundidad en capas específicas. |

## 9. Guardrails y anti-racionalizaciones

- Si un dato no existe en la API activa, la salida debe marcarlo explícitamente como [N/A].
- No usar fuentes externas para completar lesionados, corners, alineaciones o noticias si la skill está definida como API única.
- No convertir correlaciones débiles o señales opcionales en afirmaciones centrales.
- No esconder contradicciones entre mercado, modelo y señales contextuales.
- No rellenar capas con prosa vacía: cada capa debe decir algo concreto o admitir que no tiene base suficiente.

## 10. Formato de salida recomendado

El informe final debe mantener siempre el mismo orden: título del partido, 8 capas, confianza global y cierre prudente. Los datos faltantes deben mostrarse como [N/A] con razón breve. Las señales fuertes, moderadas y débiles deben ir preferiblemente en listas, no enterradas en párrafos largos.

## 11. Cómo migrar la skill a otra API

**Paso 1 — Inventario de cobertura**  
Listar qué endpoints equivalentes existen para: eventos, odds, predicción ML, forma, H2H, player-stats y señales opcionales.

**Paso 2 — Tabla de mapeo**  
Crear una matriz “necesidad lógica → endpoint/campo real”. Todo lo no mapeado debe quedar como [N/A].

**Paso 3 — Revalidación de capas**  
Verificar capa por capa qué sigue siendo posible, qué se degrada y qué deja de existir.

**Paso 4 — Reescritura de guardrails**  
Actualizar qué cosas ya no se pueden asumir y cuáles nuevas sí pueden entrar.

**Paso 5 — Casos de prueba**  
Probar al menos: partido con cobertura completa, partido sin ML, partido sin odds, partido con signals opcionales, partido ambiguo y partido ya iniciado.

## 12. Checklist de validación antes de dar la skill por buena

- ¿Existe un endpoint real para cada dato que la skill afirma usar?
- ¿Hay alguna parte que asuma implícitamente corners, lesionados o alineaciones sin cobertura real?
- ¿La capa predictiva depende de odds y/o ML, o se coló un pseudo-modelo escondido?
- ¿Las capas opcionales degradan bien cuando faltan datos?
- ¿El output final suena prudente o vende seguridad?
- ¿La migración a otra API requeriría solo remapear datos y no reescribir la filosofía de análisis?
