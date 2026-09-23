# SPEC - Asistente del Hospital Arroyo Claro

Especificacion tecnica derivada de `mission.md`. Cada seccion define el contrato
que el codigo tiene que cumplir y como se verifica.

---

## Parte 1 - Recuperador vectorial

### Contrato

```bash
python recuperar.py --preguntas datos/preguntas_recuperacion_dev.jsonl --salida resultados.jsonl
```

Entrada: JSONL con al menos `{"id": ..., "pregunta": ...}`.
Salida: JSONL, una linea por pregunta, en el mismo orden de entrada:

```json
{"id": "R01", "fragmentos": ["texto mas relevante", "siguiente", "..."]}
```

### Pipeline

1. **Carga**: lee `datos/corpus/*.md`, ordenados alfabeticamente (determinismo).
2. **Chunking**: estrategia configurable.
   - `estructura`: corta por encabezados Markdown (`#`, `##`, `###`), y parte
     las secciones que superan `max_tokens` respetando limites de parrafo.
   - `ventana`: ventana deslizante de `tamano` palabras con `solapamiento`.
   - Opcional `prefijo_metadatos`: antepone "titulo del doc > titulo de seccion"
     al texto del fragmento antes de embeber.
3. **Embeddings**: encoder configurable (ver abajo), normalizados a norma 1.
4. **Busqueda**: coseno (producto punto sobre vectores normalizados),
   se devuelven los `top_k` por encima de `umbral`.

### Encoders a comparar (minimo 3)

| clave | modelo | notas |
|---|---|---|
| `bert_base` | `dccuchile/bert-base-spanish-wwm-cased` | **linea de base obligatoria**: mean pooling de la ultima capa, sin ajuste para similitud |
| `minilm` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | sentence-transformer |
| `e5_small` | `intfloat/multilingual-e5-small` | requiere prefijos `query: ` / `passage: ` |
| `e5_base` | `intfloat/multilingual-e5-base` | idem, mas grande |
| `bge_m3` | `BAAI/bge-m3` | opcional, el mas caro en CPU |

Todos corren en CPU. El mean pooling ignora los tokens de padding via
attention mask.

### Metrica

`context_relevance` = media armonica de recall y precision de evidencia,
promediada sobre preguntas. **Es el numero a maximizar.** Baseline lexico
ingenuo = 0,35.

El evaluador compara la evidencia como **subcadena literal** del fragmento
devuelto, previa normalizacion (minusculas y espacios colapsados; los acentos
NO se sacan). Dos consecuencias:

1. El chunking no puede reescribir el texto: se devuelve el fragmento crudo, y
   el prefijo de metadatos se usa solo para embeber.
2. `precision` = fragmentos devueltos con evidencia / fragmentos devueltos, asi
   que con la evidencia en un solo fragmento el CR topea en `2/(top_k+1)`.
   Medido en `experimentos/techo_chunking.py`: con corte por estructura, las 20
   preguntas dev tienen su evidencia en UN fragmento. De ahi `top_k: 1`.

### Evidencia obligatoria

Una fila por configuracion en la tabla del INFORME, cada una con su
`experimentos/<nombre>.eval.json`. Sin archivo, la fila no cuenta.

### Criterio de exito

La config entregada le gana con claridad a `bert_base`, y el INFORME explica
con numeros por que gano el encoder elegido.

---

## Parte 2 - Agente con tool calling

Modelo: `deepseek/deepseek-v4-flash-0731` via OpenRouter, con `ChatOpenAI`
de `langchain-openai` y `base_url="https://openrouter.ai/api/v1"`.

### Herramientas (nombres exactos, los usa el evaluador)

| nombre | fuente |
|---|---|
| `buscar_documentos(consulta)` | recuperador de la parte 1 |
| `consultar_camas(sector)` | `GET /camas` |
| `consultar_guardia(especialidad)` | `GET /guardia` |
| `consultar_turnos(especialidad)` | `GET /turnos` |
| `consultar_farmacia(medicamento)` | `GET /farmacia` |
| `consultar_espera()` | `GET /espera` |

API en `http://localhost:8765`.

### Contrato

```bash
python agente.py --preguntas datos/preguntas_agente_dev.jsonl --salida respuestas.jsonl
```

```json
{"id": "A01", "respuesta": "...", "contextos": ["..."], "herramientas": ["buscar_documentos"]}
```

`contextos` lleva **todo** lo que el agente recibio de sus herramientas,
como texto (fragmentos y JSON de la API serializado).

### Log obligatorio

Un `.md` por corrida con, por pregunta: llamadas a herramientas con argumentos
y resultados, la respuesta, y el usage (tokens in/out y costo) de cada llamada
al modelo. **Sin log, la parte vale cero.**

### Criterio de exito

Ruteo cercano a 1 y Context Relevance / Answer Faithfulness / Answer Relevance
por encima de 4 en `dev`.

---

## Parte 3 - Servidor MCP

`servidor_mcp.py` expone las mismas seis herramientas por stdio con el SDK
oficial `mcp`. `agente_mcp.py` las descubre con `tools/list` y las invoca con
`tools/call`, cargadas como tools de LangChain via `langchain-mcp-adapters`.

**Restriccion**: `agente_mcp.py` no puede tener codigo propio para consultar la
API ni el recuperador. Todo sale del servidor.

Verificacion adicional: MCP Inspector (`npx @modelcontextprotocol/inspector
python servidor_mcp.py`), llamando a las seis herramientas; capturas en
`experimentos/inspector/`.

---

## Parte 4 - Atencion en NumPy

`atencion.py`, **solo NumPy**, con `softmax`, `atencion`, `autoatencion`
(mascara causal opcional), `multicabeza` y `layer_norm`.

```bash
python atencion/test_atencion.py atencion.py
```

Criterio de exito: los 14 tests en verde con el archivo de la catedra sin tocar.

### Firmas (reconciliadas con `atencion/test_atencion.py`)

```python
softmax(M)                                  # softmax por fila (ultimo eje)
atencion(Q, K, V, mascara=False)            -> (salida, A)
autoatencion(X, Wq, Wk, Wv, mascara=False)  -> (salida, A)
multicabeza(X, cabezas, Wo, mascara=False)  -> salida
layer_norm(x, eps=1e-5)                     # media 0 y varianza 1 por fila
```

`cabezas` es una lista de ternas `(Wq, Wk, Wv)`, una por cabeza; las salidas se
concatenan sobre la dimension de rasgos y `Wo` las mezcla. `mascara=True` aplica
la mascara causal. `d_v` no tiene por que ser igual a `d_k`.

**Estado: 14/14 en verde.**

---

## Parte 5 - A mano

`a_mano/` con las hojas escaneadas. **Sin IA.**
