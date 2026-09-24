# Informe — Asistente del Hospital Arroyo Claro

**Fecha de actualización:** 24 de septiembre de 2026  
**Estado:** avance parcial; Parte 1 completa y partes 2, 3 y 5 pendientes.

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

Todavía pendiente. Falta implementar agente.py, las seis herramientas, la integración con OpenRouter, las corridas del benchmark, los archivos de respuestas y los logs con tokens y costos.

### Parte 3 — Servidor MCP

Todavía pendiente. Falta implementar servidor_mcp.py y agente_mcp.py, probar las seis herramientas con MCP Inspector, guardar las capturas y generar la evaluación comparativa con la Parte 2.

### Parte 4 — Atención en NumPy

Completada antes de este informe. atencion.py pasa los 14 tests entregados por la cátedra y los 48 tests propios del repositorio también pasan.

### Parte 5 — Bloque de transformer a mano

Pendiente y debe resolverse sin IA. Falta completar las cuentas manuscritas, las cinco preguntas finales y guardar los escaneos en a_mano/.

## 4. Entregables incorporados en este avance

- configuración ganadora en config.yaml;
- 18 resultados JSONL de experimentos;
- 18 evaluaciones .eval.json reproducibles;
- resultado validado de la configuración ganadora en experimentos/ganadora.jsonl.eval.json;
- este informe parcial.

El informe deberá ampliarse al completar las Partes 2, 3 y 5, incluyendo los resultados de los agentes, el análisis de fallos, la comparación MCP y el costo total de la misión.

