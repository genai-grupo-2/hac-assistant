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

```
recuperar.py          # CLI parte 1 (thin wrapper sobre recuperador/)
agente.py             # CLI parte 2
servidor_mcp.py       # parte 3, transporte stdio
agente_mcp.py         # CLI parte 3
atencion.py           # parte 4, solo NumPy
config.yaml           # config ganadora de la parte 1
recuperador/          # logica del RAG (chunking, encoders, indice)
tests/                # tests propios (pytest); NO es el de la catedra
experimentos/         # un .eval.json por configuracion probada
a_mano/               # parte 5, escaneos
INFORME.md            # entregable final
```

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
