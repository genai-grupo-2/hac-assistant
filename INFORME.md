# Informe — Asistente del Hospital Arroyo Claro

**Fecha de actualización:** 30 de septiembre de 2026
**Estado:** Partes 1, 2 y 4 completas; Parte 3 implementada y evaluada, con capturas del Inspector pendientes; Parte 5 pendiente.

## 1. Resumen ejecutivo

Se implementó y midió el recuperador vectorial de la Parte 1 sobre los 20 documentos del corpus del hospital y las 20 preguntas de desarrollo. Se compararon tres encoders, dos estrategias de chunking y tres valores de top_k, con 18 configuraciones evaluadas mediante el evaluador oficial.

La configuración fijada para la entrega es:

    encoder: e5_small
    chunking:
      estrategia: estructura
      max_palabras: 180
      prefijo_metadatos: true
    busqueda:
      top_k: 1
      umbral: 0.0
      margen: 0.0

En el conjunto dev, esta configuración obtuvo context_relevance = 0.90, recall = 0.90 y precision = 0.90. La línea de base obligatoria BERT, con la misma estrategia de chunking y top_k=1, obtuvo context_relevance = 0.40.

## 2. Parte 1 — RAG vectorial

### 2.1 Implementación

El pipeline está compuesto por:

- carga determinista de datos/corpus/*.md en orden alfabético;
- chunking por estructura Markdown o por ventana deslizante;
- prefijo opcional de metadatos para el embedding;
- embeddings normalizados a norma 1;
- búsqueda por producto punto, equivalente al coseno entre vectores normalizados;
- salida JSONL compatible con el contrato de la cátedra.

El comando de entrega queda definido por:

    python recuperar.py --preguntas datos/preguntas_recuperacion_dev.jsonl --salida resultados.jsonl

La configuración ganadora está en config.yaml. La lógica del recuperador se encuentra en retriever/ y el CLI en recuperar.py.

### 2.2 Diseño experimental

Se evaluaron los siguientes encoders:

- bert_base: BERT en español sin ajuste específico para similitud, usado como línea de base obligatoria;
- minilm: paraphrase-multilingual-MiniLM-L12-v2;
- e5_small: multilingual-e5-small, con los prefijos query: y passage:.

Se compararon dos estrategias:

- estructura: corte por encabezados Markdown, con tope de 180 palabras;
- ventana150_40: ventanas de 150 palabras con 40 palabras de solapamiento.

Para cada combinación se midieron top_k=1, top_k=2 y top_k=3, con umbral de similitud 0.0. Cada configuración tiene su archivo de resultados y su archivo .eval.json en experimentos/.

### 2.3 Resultados

| Encoder | Chunking | top_k | Context relevance | Recall | Precision | MRR |
|---|---|---:|---:|---:|---:|---:|
| BERT base | estructura | 1 | 0.4000 | 0.4000 | 0.4000 | 0.4000 |
| BERT base | estructura | 2 | 0.3667 | 0.5500 | 0.2750 | 0.4750 |
| BERT base | estructura | 3 | 0.3250 | 0.6500 | 0.2167 | 0.5083 |
| BERT base | ventana 150/40 | 1 | 0.4500 | 0.4500 | 0.4500 | 0.4500 |
| BERT base | ventana 150/40 | 2 | 0.3333 | 0.5000 | 0.2500 | 0.4750 |
| BERT base | ventana 150/40 | 3 | 0.3000 | 0.6000 | 0.2000 | 0.5083 |
| MiniLM | estructura | 1 | 0.9000 | 0.9000 | 0.9000 | 0.9000 |
| MiniLM | estructura | 2 | 0.6667 | 1.0000 | 0.5000 | 0.9500 |
| MiniLM | estructura | 3 | 0.5000 | 1.0000 | 0.3333 | 0.9500 |
| MiniLM | ventana 150/40 | 1 | 0.8500 | 0.8500 | 0.8500 | 0.8500 |
| MiniLM | ventana 150/40 | 2 | 0.6000 | 0.9000 | 0.4500 | 0.8750 |
| MiniLM | ventana 150/40 | 3 | 0.4750 | 0.9500 | 0.3167 | 0.8917 |
| E5-small | estructura | 1 | **0.9000** | 0.9000 | **0.9000** | 0.9000 |
| E5-small | estructura | 2 | 0.6333 | 0.9500 | 0.4750 | 0.9250 |
| E5-small | estructura | 3 | 0.5000 | 1.0000 | 0.3333 | 0.9417 |
| E5-small | ventana 150/40 | 1 | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| E5-small | ventana 150/40 | 2 | 0.6833 | 1.0000 | 0.5250 | 0.9000 |
| E5-small | ventana 150/40 | 3 | 0.5150 | 1.0000 | 0.3500 | 0.9000 |

Los valores completos por pregunta están en los archivos experimentos/*.jsonl.eval.json; por ejemplo, experimentos/e5_small_estructura_k1.jsonl.eval.json.

### 2.4 Elección de la configuración final

La estrategia estructural fue preferible porque el diagnóstico de chunking mostró que mantiene toda la evidencia de las 20 preguntas dentro de un único fragmento. Esto hace posible que top_k=1 alcance simultáneamente recall y precision altos.

top_k mayores aumentan el recall, pero agregan fragmentos sin evidencia y reducen la precision. Por ejemplo, E5-small con chunking estructural pasa de context_relevance=0.90 con top_k=1 a 0.6333 con top_k=2 y 0.50 con top_k=3.

MiniLM y E5-small empatan en 0.90 con chunking estructural y top_k=1. Se seleccionó E5-small porque cumple el empate en la configuración principal, supera a MiniLM en la variante de ventana con top_k=2 (0.6833 contra 0.6000) y ya está integrado en la configuración reproducible del proyecto.

La mejora frente a BERT es de 0.50 puntos absolutos de context_relevance —de 0.40 a 0.90—, por lo que supera con claridad la línea de base solicitada.

### 2.5 Reproducibilidad y validaciones

Se instalaron las dependencias de requirements.txt y se ejecutaron:

    python -m pytest -q
    # 48 passed

    python atencion/test_atencion.py atencion.py
    # 14 tests, OK

La evaluación de recuperación no utiliza un juez LLM, por lo que estas corridas de la Parte 1 no generaron costo de OpenRouter.

## 3. Estado de las partes restantes

### Parte 2 — Agente con tool calling

La implementación está completa en agente.py y tools/hospital_api.py. Las seis
tools fueron verificadas contra la API local y el ciclo de tool calling tiene
pruebas offline.

Se ejecutó el benchmark completo de 12 preguntas con el modelo indicado. Los
artefactos son respuestas.jsonl, respuestas.jsonl.eval.json y respuestas.log.md.
Los resultados fueron:

- ruteo: **1.000**;
- Context Relevance: **4.917/5**;
- Answer Faithfulness: **5.000/5**;
- Answer Relevance: **4.917/5**;
- costo del juez: **USD 0.01852**.

Las 12 preguntas tuvieron ruteo perfecto. La única pregunta que no obtuvo 5
en todas las dimensiones fue A11, con Context Relevance y Answer Relevance 4;
Faithfulness y ruteo fueron 5 y 1.0 respectivamente. El log conserva las
llamadas, argumentos, respuestas y usage de cada llamada al modelo.

### Parte 3 — Servidor MCP

La implementación está completa en `servidor_mcp.py` y `agente_mcp.py`. El
servidor usa transporte `stdio` y el SDK oficial `mcp`; publica las seis
herramientas exigidas. El cliente abre una sesión MCP, descubre las herramientas
con `tools/list` mediante `langchain-mcp-adapters` y las ejecuta con
`tools/call`. No contiene código propio de acceso a la API ni al recuperador:
esas implementaciones viven en `tools/hospital_tools.py` y son compartidas con
la Parte 2.

Se ejecutó el benchmark completo de 12 preguntas. Los artefactos son
`respuestas_mcp.jsonl`, `respuestas_mcp.jsonl.eval.json` y
`respuestas_mcp.log.md`. Los resultados fueron:

- ruteo: **1.000**;
- Context Relevance: **5.000/5**;
- Answer Faithfulness: **5.000/5**;
- Answer Relevance: **5.000/5**;
- costo del agente: **USD 0.00347494**;
- costo del juez: **USD 0.01923**.

Las seis herramientas también se descubrieron y llamaron correctamente desde
MCP Inspector. Todavía falta guardar las capturas de esa verificación en
`experimentos/inspector/` para cerrar el entregable visual obligatorio.

#### Comparación Parte 2 vs. Parte 3

| Implementación | Context Relevance | Faithfulness | Answer Relevance | Ruteo | Costo agente | Costo juez | Costo corrida |
|---|---:|---:|---:|---:|---:|---:|---:|
| LangChain directo | 4.917 | 5.000 | 4.917 | 1.000 | USD 0.00327254 | USD 0.01852 | USD 0.02179254 |
| LangChain + MCP | **5.000** | **5.000** | **5.000** | 1.000 | USD 0.00347494 | USD 0.01923 | USD 0.02270494 |

El ruteo se mantuvo perfecto. La corrida MCP mejoró A11: el nuevo muestreo del
modelo incluyó todos los requisitos documentales y llevó Context Relevance y
Answer Relevance de 4 a 5. No se atribuye esa diferencia al transporte MCP,
porque el prompt, el modelo y las fuentes son los mismos y el modelo es
generativo. El costo del agente MCP fue USD 0.00020240 mayor; la diferencia es
compatible con una salida algo más larga y se verifica en los logs de usage.

### Parte 4 — Atención en NumPy

Completada antes de este informe. atencion.py pasa los 14 tests entregados por la cátedra y los 48 tests propios del repositorio también pasan.

### Parte 5 — Bloque de transformer a mano

Pendiente y debe resolverse sin IA. Falta completar las cuentas manuscritas, las cinco preguntas finales y guardar los escaneos en a_mano/.

## 4. Entregables incorporados en este avance

- configuración ganadora en config.yaml;
- 18 resultados JSONL de experimentos;
- 18 evaluaciones .eval.json reproducibles;
- resultado validado de la configuración ganadora en experimentos/ganadora.jsonl.eval.json;
- cliente de la API y agente LangChain de la Parte 2;
- prueba offline del ciclo de tool calling;
- respuestas, evaluación y log del benchmark de la Parte 2;
- servidor y cliente MCP de la Parte 3;
- respuestas, evaluación y log del benchmark MCP;
- este informe parcial.

El costo acumulado de las dos corridas de agentes y sus evaluaciones es
**USD 0.04449748**. La Parte 1 no usó juez y no generó costo de OpenRouter.
Antes de la entrega falta contrastar este total con el dashboard de actividad,
incorporar las capturas del MCP Inspector y completar la Parte 5.
