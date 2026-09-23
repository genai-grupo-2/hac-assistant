# Roadmap — Asistente del Hospital Arroyo Claro

Entrega: **viernes 9 de octubre de 2026**. Consigna completa en [`mission.md`](mission.md),
contratos técnicos en [`SPEC.md`](SPEC.md), convenciones en [`CLAUDE.md`](CLAUDE.md).

Estado a **2026-09-23**.

## Estado general

| Parte | Puntos | Estado |
|---|---|---|
| 1 — RAG vectorial | 25 | 🟡 código listo, **sin medir** (falta el corpus) |
| 2 — Agente con tool calling | 30 | ⬜ no empezada |
| 3 — Servidor MCP | 15 | ⬜ no empezada |
| 4 — Atención en NumPy | 15 | 🟡 implementada, **falta el test oficial** |
| 5 — Bloque a mano | 15 | ⬜ no empezada (sin IA) |

## 🚧 Bloqueante: falta el andamiaje de la cátedra

El repo **no tiene** nada de lo que `mission.md` da por existente. Sin esos
archivos no se puede medir nada, y sin medición las partes 1 a 3 no puntúan.

| Falta | Bloquea |
|---|---|
| `datos/corpus/` (20 documentos .md) | F5, y toda la medición de la parte 1 |
| `datos/preguntas_recuperacion_dev.jsonl` | F5 |
| `datos/preguntas_agente_dev.jsonl` | F7, F9 |
| `evaluar/evaluar.py` | F5, F7, F9 |
| `api/servidor.py` + `api/README.md` | F6, F7, F8 |
| `atencion/test_atencion.py` | F2 (cierre) |

Hay que clonar/copiar el material de la cátedra dentro del repo antes de seguir.

## Features

### Tercio 1 — hecho

| # | Feature | Dónde | Estado |
|---|---|---|---|
| F1 | Scaffolding del proyecto | `CLAUDE.md`, `SPEC.md`, `ROADMAP.md`, `requirements.txt`, `pytest.ini` | ✅ |
| F2 | Atención en NumPy (parte 4) | `atencion.py`, `tests/test_attention.py` | 🟡 24 tests propios en verde; falta correr el de la cátedra |
| F3 | Chunking + configuración | `retriever/corpus.py`, `retriever/chunking.py`, `retriever/config.py`, `config.yaml` | ✅ |
| F4 | Encoders + índice + CLI | `retriever/encoders.py`, `retriever/index.py`, `recuperar.py` | ✅ código; encoders nunca ejecutados (falta descargar modelos) |

Detalle de lo entregado:

- **`atencion.py`** — `softmax`, `atencion`, `autoatencion` (máscara causal
  opcional), `multicabeza`, `layer_norm`. Solo NumPy, con dimensiones de batch
  a la izquierda. ⚠️ Las firmas están **asumidas** (ver `SPEC.md` § Parte 4):
  `atencion` y compañía devuelven `(salida, pesos)`. Hay que reconciliarlas
  cuando llegue `atencion/test_atencion.py`.
- **`retriever/`** — chunking por estructura Markdown o por ventana
  deslizante, prefijo opcional de metadatos, catálogo de 6 encoders
  (`bert_base` y `bert_multi` como línea de base con mean pooling; `minilm`,
  `e5_small`, `e5_base` con prefijos `query:`/`passage:`, `bge_m3`), índice
  denso con coseno exacto, top-k y umbral.
- **`config.yaml`** — la config que correrá la cátedra. Hoy tiene valores de
  arranque **no medidos**; se reemplaza por la fila ganadora de F5.
- **Tests** — 45 en verde (`python -m pytest`), sin descargar ningún modelo:
  usan un encoder falso de bolsa de palabras.

### Tercio 2 — próximo

| # | Feature | Entregable | Depende de |
|---|---|---|---|
| F5 | Barrido de experimentos de la parte 1 | `experimentos/*.eval.json`, tabla, `config.yaml` final | corpus + preguntas + `evaluar.py` |
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
| Firmas de `atencion.py` distintas a las del test de la cátedra | adaptar apenas llegue el archivo; la lógica no cambia |
| Tunear contra `dev` y caer en test | mantener el barrido chico y preferir configs simples que ganen por margen, no por décimas |
| Costo del juez de OpenRouter | correr el evaluador solo ante un cambio que valga la pena medir; registrar el costo por corrida en los logs |
| `bge_m3` muy lento en CPU | es opcional; con 3 encoders alcanza para la consigna |
