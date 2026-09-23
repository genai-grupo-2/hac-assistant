#!/usr/bin/env python3
"""Parte 1: recuperador vectorial sobre el corpus del hospital.

    python recuperar.py --preguntas datos/preguntas_recuperacion_dev.jsonl \
                        --salida resultados.jsonl

La configuracion vive en `config.yaml`, no en flags, porque la catedra corre
este comando tal cual sobre las preguntas de test. Los flags opcionales existen
solo para el barrido de experimentos.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from retriever.config import Config, cargar_config
from retriever.index import Indice

# La consigna no fija el nombre del campo de la pregunta; se aceptan los
# candidatos razonables para no romper si el JSONL usa otro.
CLAVES_PREGUNTA = ("pregunta", "consulta", "texto", "question", "query")


def leer_preguntas(ruta: str | Path) -> list[dict]:
    """Lee un JSONL, salteando lineas en blanco."""
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lineas if l.strip()]


def texto_de(pregunta: dict) -> str:
    for clave in CLAVES_PREGUNTA:
        if isinstance(pregunta.get(clave), str) and pregunta[clave].strip():
            return pregunta[clave]
    raise KeyError(
        f"la pregunta {pregunta.get('id', '?')} no tiene ningun campo de texto "
        f"entre {CLAVES_PREGUNTA}"
    )


def recuperar(preguntas: list[dict], indice: Indice) -> list[dict]:
    """Una linea de salida por pregunta, en el orden de entrada."""
    salida = []
    for pregunta in preguntas:
        resultados = indice.buscar(texto_de(pregunta))
        salida.append(
            {
                "id": pregunta.get("id"),
                "fragmentos": [r.fragmento.texto for r in resultados],
            }
        )
    return salida


def escribir_jsonl(filas: list[dict], ruta: str | Path) -> None:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")


def construir_config(args: argparse.Namespace) -> Config:
    """Config del YAML, con los flags del barrido pisando lo que corresponda."""
    cfg = cargar_config(args.config)
    cambios: dict = {}
    if args.encoder:
        cambios["encoder"] = args.encoder
    chunking = {
        k: v
        for k, v in (
            ("estrategia", args.estrategia),
            ("max_palabras", args.max_palabras),
            ("tamano", args.tamano),
            ("solapamiento", args.solapamiento),
        )
        if v is not None
    }
    if chunking:
        cambios["chunking"] = chunking
    busqueda = {
        k: v
        for k, v in (("top_k", args.top_k), ("umbral", args.umbral), ("margen", args.margen))
        if v is not None
    }
    if busqueda:
        cambios["busqueda"] = busqueda
    return cfg.con(**cambios) if cambios else cfg


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--preguntas", required=True, help="JSONL de preguntas")
    p.add_argument("--salida", required=True, help="JSONL de resultados")
    p.add_argument("--config", default=None, help="YAML de configuracion")
    # Solo para experimentos; la entrega usa config.yaml.
    p.add_argument("--encoder", default=None)
    p.add_argument("--estrategia", default=None, choices=["estructura", "ventana"])
    p.add_argument("--max-palabras", dest="max_palabras", type=int, default=None)
    p.add_argument("--tamano", type=int, default=None)
    p.add_argument("--solapamiento", type=int, default=None)
    p.add_argument("--top-k", dest="top_k", type=int, default=None)
    p.add_argument("--umbral", type=float, default=None)
    p.add_argument("--margen", type=float, default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)
    cfg = construir_config(args)

    preguntas = leer_preguntas(args.preguntas)
    indice = Indice.construir(cfg)
    print(
        f"[recuperar] encoder={cfg.encoder} chunking={cfg.chunking.estrategia} "
        f"fragmentos={len(indice)} top_k={cfg.busqueda.top_k} "
        f"umbral={cfg.busqueda.umbral} margen={cfg.busqueda.margen}",
        file=sys.stderr,
    )

    escribir_jsonl(recuperar(preguntas, indice), args.salida)
    print(f"[recuperar] {len(preguntas)} preguntas -> {args.salida}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
