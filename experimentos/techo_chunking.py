#!/usr/bin/env python3
"""Diagnostico del chunking contra el corpus real. No usa ningun modelo.

Antes de gastar tiempo comparando encoders conviene saber una cosa: si el
troceado parte una frase de evidencia al medio, **ningun** encoder puede
recuperarla, porque el evaluador busca la evidencia como subcadena literal del
fragmento devuelto (`evaluar/evaluar.py`, funcion `recuperacion`).

Este script mide, para cada configuracion de chunking:

- `evidencia_perdida`: frases de evidencia que no entran enteras en ningun
  fragmento. Es perdida irrecuperable.
- `techo_cr`: el context_relevance que sacaria un recuperador perfecto, uno que
  devuelve exactamente los fragmentos con evidencia y nada mas. Es la cota
  superior de esa configuracion.
- `fragmentos_por_pregunta`: cuantos fragmentos hacen falta en promedio, que es
  el top_k al que conviene apuntar.

Uso:
    python experimentos/techo_chunking.py
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from evaluar.evaluar import norm  # se usa la misma normalizacion que la catedra
from retriever.chunking import trocear
from retriever.config import ConfigChunking
from retriever.corpus import cargar_corpus

PREGUNTAS = RAIZ / "datos" / "preguntas_recuperacion_dev.jsonl"

CONFIGURACIONES = {
    "estructura_180": ConfigChunking(estrategia="estructura", max_palabras=180),
    "estructura_120": ConfigChunking(estrategia="estructura", max_palabras=120),
    "estructura_80": ConfigChunking(estrategia="estructura", max_palabras=80),
    "estructura_300": ConfigChunking(estrategia="estructura", max_palabras=300),
    "ventana_150_40": ConfigChunking(estrategia="ventana", tamano=150, solapamiento=40),
    "ventana_80_30": ConfigChunking(estrategia="ventana", tamano=80, solapamiento=30),
    "ventana_60_20": ConfigChunking(estrategia="ventana", tamano=60, solapamiento=20),
}


def cr(recall: float, precision: float) -> float:
    """Media armonica, igual que el evaluador."""
    if recall + precision == 0:
        return 0.0
    return 2 * recall * precision / (recall + precision)


def evaluar_config(nombre: str, cfg: ConfigChunking, preguntas: list[dict]) -> dict:
    fragmentos = trocear(cargar_corpus(RAIZ / "datos" / "corpus"), cfg)
    normalizados = [norm(f.texto) for f in fragmentos]

    perdidas: list[tuple[str, str]] = []
    crs: list[float] = []
    ks: list[int] = []

    for p in preguntas:
        evidencias = [norm(e) for e in p["evidencia"]]
        # Los fragmentos que un recuperador perfecto devolveria.
        utiles = {i for i, f in enumerate(normalizados) if any(e in f for e in evidencias)}
        encontradas = [e for e in evidencias if any(e in f for f in normalizados)]

        for e, cruda in zip(evidencias, p["evidencia"]):
            if not any(e in f for f in normalizados):
                perdidas.append((p["id"], cruda))

        recall = len(encontradas) / len(evidencias)
        precision = 1.0 if utiles else 0.0   # por construccion, todos son utiles
        crs.append(cr(recall, precision))
        ks.append(len(utiles))

    return {
        "config": nombre,
        "fragmentos_totales": len(fragmentos),
        "palabras_por_fragmento": round(
            sum(len(f.texto.split()) for f in fragmentos) / len(fragmentos), 1
        ),
        "evidencia_perdida": len(perdidas),
        "techo_cr": round(sum(crs) / len(crs), 4),
        "fragmentos_por_pregunta": round(sum(ks) / len(ks), 2),
        "max_fragmentos_una_pregunta": max(ks),
        "detalle_perdidas": perdidas,
    }


def main() -> int:
    preguntas = [
        json.loads(l)
        for l in PREGUNTAS.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]

    filas = [evaluar_config(n, c, preguntas) for n, c in CONFIGURACIONES.items()]

    cabecera = f"{'config':<18}{'frags':>7}{'pal/frag':>10}{'perdida':>9}{'techo_cr':>10}{'k medio':>9}{'k max':>7}"
    print(cabecera)
    print("-" * len(cabecera))
    for f in filas:
        print(
            f"{f['config']:<18}{f['fragmentos_totales']:>7}{f['palabras_por_fragmento']:>10}"
            f"{f['evidencia_perdida']:>9}{f['techo_cr']:>10}"
            f"{f['fragmentos_por_pregunta']:>9}{f['max_fragmentos_una_pregunta']:>7}"
        )

    for f in filas:
        if f["detalle_perdidas"]:
            print(f"\n[{f['config']}] evidencia que no entra en ningun fragmento:")
            for pid, ev in f["detalle_perdidas"]:
                print(f"  {pid}: {ev!r}")

    destino = Path(__file__).with_suffix(".json")
    destino.write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
