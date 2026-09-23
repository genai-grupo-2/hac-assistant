# Roadmap — Asistente del Hospital Arroyo Claro

Entrega: **viernes 9 de octubre de 2026**. Consigna completa en [`mission.md`](mission.md),
contratos técnicos en [`SPEC.md`](SPEC.md), convenciones en [`CLAUDE.md`](CLAUDE.md).

Estado a **2026-09-23**.

## Estado general

| Parte | Puntos | Estado |
|---|---|---|
| 1 — RAG vectorial | 25 | 🟡 pipeline listo y chunking validado; falta medir encoders (F5) |
| 2 — Agente con tool calling | 30 | ⬜ no empezada |
| 3 — Servidor MCP | 15 | ⬜ no empezada |
| 4 — Atención en NumPy | 15 | ✅ **14/14 tests de la cátedra en verde** |
| 5 — Bloque a mano | 15 | ⬜ no empezada (sin IA; consigna en `a_mano/ejercicio.md`) |

## Material de la cátedra

✅ Ya está todo en el repo (mergeado el 2026-09-23): `datos/corpus/` con los 20
documentos, las dos tandas de preguntas dev, `evaluar/evaluar.py`,
`api/servidor.py` + `api/datos_api.json`, `atencion/test_atencion.py` y
`a_mano/ejercicio.md`. Nada de eso se modifica.

Falta solo **instalar las dependencias** (`pip install -r requirements.txt`):
`torch` y `sentence-transformers` son ~2 GB y hasta que no estén no se puede
correr ningún encoder de verdad.

## Hallazgo: el top-k es la decisión que más pesa

`evaluar/evaluar.py` calcula `precision` = fragmentos devueltos que contienen
evidencia / fragmentos devueltos, y `context_relevance` es la media armónica con
el recall. Si la evidencia vive en **un solo** fragmento, devolver k fragmentos
topea el CR en `2/(k+1)`:

| top_k | CR máximo posible |
|---|---|
| 1 | 1,00 |
| 2 | 0,67 |
| 3 | 0,50 |
| 4 | 0,40 |

`experimentos/techo_chunking.py` (corre sin modelos) mide el techo de cada
chunking contra el corpus real:

| config | frags | pal/frag | evidencia perdida | techo CR | k medio | k máx |
|---|---|---|---|---|---|---|
| estructura (80–300) | 53–55 | ~41 | **0** | 1,00 | **1,00** | **1** |
| ventana 150/40 | 26 | 104 | 0 | 1,00 | 1,05 | 2 |
| ventana 80/30 | 47 | 70 | 0 | 1,00 | 1,20 | 2 |
| ventana 60/20 | 59 | 55 | 0 | 1,00 | 1,25 | 2 |

Ningún chunking pierde evidencia, y el corte por estructura deja la evidencia de
las 20 preguntas dev dentro de un único fragmento. De ahí `top_k: 1` en
`config.yaml`: todo el problema se reduce a acertar el fragmento en el puesto 1.
Como red por si el set de test trae alguna pregunta que necesite dos fragmentos,
el índice soporta `margen`, un corte relativo al mejor score (hoy desactivado,
lo tunea F5).

## Features

### Tercio 1 — hecho

| # | Feature | Dónde | Estado |
|---|---|---|---|
| F1 | Scaffolding del proyecto | `CLAUDE.md`, `SPEC.md`, `ROADMAP.md`, `requirements.txt`, `pytest.ini` | ✅ |
| F2 | Atención en NumPy (parte 4) | `atencion.py`, `tests/test_attention.py` | ✅ 14/14 de la cátedra + 25 propios |
| F3 | Chunking + configuración | `retriever/corpus.py`, `retriever/chunking.py`, `retriever/config.py`, `config.yaml` | ✅ |
| F4 | Encoders + índice + CLI | `retriever/encoders.py`, `retriever/index.py`, `recuperar.py` | ✅ código; encoders aún no ejecutados (faltan las deps) |
| F4b | Diagnóstico de techo del chunking | `experimentos/techo_chunking.py`, `.json` | ✅ |

Detalle de lo entregado:

- **`atencion.py`** — `softmax`, `atencion`, `autoatencion`, `multicabeza`,
  `layer_norm`. Solo NumPy. **Parte 4 cerrada**: `python atencion/test_atencion.py
  atencion.py` da 14/14. Las firmas se reconciliaron con las reales (`mascara`
  es un flag booleano, no un arreglo; `multicabeza(X, cabezas, Wo)` recibe una
  lista de ternas y devuelve solo la salida).
- **`retriever/`** — chunking por estructura Markdown o por ventana
  deslizante, prefijo opcional de metadatos, catálogo de 6 encoders
  (`bert_base` y `bert_multi` como línea de base con mean pooling; `minilm`,
  `e5_small`, `e5_base` con prefijos `query:`/`passage:`, `bge_m3`), índice
  denso con coseno exacto, top-k y umbral.
- **`config.yaml`** — la config que correrá la cátedra. Hoy tiene valores de
  arranque **no medidos**; se reemplaza por la fila ganadora de F5.
- **Tests** — 48 propios en verde (`python -m pytest`), sin descargar ningún modelo:
  usan un encoder falso de bolsa de palabras.

### Tercio 2 — próximo

| # | Feature | Entregable | Depende de |
|---|---|---|---|
| F5 | Barrido de experimentos de la parte 1 | `experimentos/*.eval.json`, tabla, `config.yaml` final | `pip install -r requirements.txt` |
| F6 | Cliente de la API del hospital (5 tools) | `tools/hospital_api.py` + tests con la API levantada | `api/servidor.py` |
| F7 | Agente LangChain (parte 2) | `agente.py`, `respuestas.jsonl`, `.eval.json`, log `.md` con usage y costo | F5, F6, `OPENROUTER_API_KEY` |

F5 es lo primero: el ruteo y la fidelidad del agente dependen de que el
recuperador ya esté afinado. El barrido mínimo son 3 encoders × 2 chunkings ×
3 top-k, con `bert_base` como línea de base obligatoria.

### Tercio 3 — después

| # | Feature | Entregable | Depende de |
|---|---|---|---|
| F8 | Servidor MCP | `servidor_mcp.py` (stdio, SDK `mcp`), capturas en `experimentos/inspector/` | F6 |
| F9 | Agente cliente MCP | `agente_mcp.py`, `respuestas_mcp.jsonl`, `.eval.json`, log `.md` | F7, F8 |
| F10 | Informe | `INFORME.md` | todo lo anterior |
| F11 | Parte 5 a mano | `a_mano/` escaneado | **sin IA** |

Restricción de F9: `agente_mcp.py` no puede tener código propio para consultar
la API ni el recuperador — todo sale del servidor. Conviene que F6 quede en un
módulo que F8 importe, y que F7 y F9 compartan prompt y logger para que la
comparación de la parte 3 mida el transporte y no otra cosa.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Tunear contra `dev` y caer en test | mantener el barrido chico y preferir configs simples que ganen por margen, no por décimas |
| Costo del juez de OpenRouter | correr el evaluador solo ante un cambio que valga la pena medir; registrar el costo por corrida en los logs |
| `bge_m3` muy lento en CPU | es opcional; con 3 encoders alcanza para la consigna |
