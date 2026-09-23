# CLAUDE.md - Asistente del Hospital Arroyo Claro

Contexto de trabajo para agentes de IA sobre este repo. La consigna completa
esta en `mission.md`; esto es el "como", no el "que".

## Reglas duras

- **Nunca modificar** `evaluar/`, `api/`, `datos/` ni `atencion/test_atencion.py`.
  La catedra corre sus propias copias; un cambio local invalida la medicion.
- **Los contratos de CLI son fijos.** Cualquier cambio de flags rompe la correccion:
  ```
  python recuperar.py   --preguntas <jsonl> --salida <jsonl>
  python agente.py      --preguntas <jsonl> --salida <jsonl>
  python agente_mcp.py  --preguntas <jsonl> --salida <jsonl>
  python atencion/test_atencion.py atencion.py
  ```
- **La configuracion ganadora de la parte 1 vive en `config.yaml`**, no en flags.
  La catedra corre `recuperar.py` sin parametros extra sobre preguntas de test.
- **La parte 5 (`a_mano/`) se resuelve sin IA.** No generar contenido ahi.

## Estructura

Los nombres nuestros van en ingles. Los marcados con (*) los fija la consigna
y **no se renombran**: la catedra corre sus propios comandos contra ellos.

```
recuperar.py          # (*) CLI parte 1, thin wrapper sobre retriever/
agente.py             # (*) CLI parte 2
servidor_mcp.py       # (*) parte 3, transporte stdio
agente_mcp.py         # (*) CLI parte 3
atencion.py           # (*) parte 4, solo NumPy
datos/                # (*) material de la catedra: corpus y preguntas
api/                  # (*) API del hospital, de la catedra
evaluar/              # (*) evaluador de la catedra
atencion/             # (*) test_atencion.py de la catedra
experimentos/         # (*) un .eval.json por configuracion probada
experimentos/inspector/  # (*) capturas del MCP Inspector
a_mano/               # (*) parte 5, escaneos
INFORME.md            # (*) entregable final
config.yaml           # config ganadora de la parte 1
retriever/            # logica del RAG (chunking, encoders, index)
tools/                # cliente de la API del hospital, compartido por 2 y 3
tests/                # tests propios (pytest); NO son los de la catedra
```

Tampoco se renombran los identificadores que la catedra invoca por nombre: las
funciones de `atencion.py` (`softmax`, `atencion`, `autoatencion`,
`multicabeza`, `layer_norm`), los nombres de las seis herramientas
(`buscar_documentos`, `consultar_camas`, ...) y los flags `--preguntas` /
`--salida`.

## Forma de trabajo

- **TDD**: test primero en `tests/`, despues implementacion.
- **Commits chicos y atomicos**, en castellano, prefijo `feat|fix|test|docs|chore`.
- **Determinismo**: semillas fijas, y el orden de los fragmentos del corpus
  ordenado alfabeticamente para que dos corridas den lo mismo.
- **Sin numeros inventados**: toda cifra del INFORME sale de un `.eval.json`
  versionado en `experimentos/`.

## Costos

Todo LLM pasa por OpenRouter (`OPENROUTER_API_KEY`). El juez del evaluador
cobra por corrida: correrlo solo cuando hay un cambio que valga la pena medir.
Cada corrida del agente loguea usage (tokens in/out y costo) por llamada.

## Convenciones de codigo

- Python 3.12, type hints en firmas publicas, docstrings cortos en castellano.
- Sin acentos en identificadores; el texto de usuario si los lleva.
- Nada de estado global mutable: la config se pasa explicita.
