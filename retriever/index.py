"""Indice vectorial en memoria y busqueda por coseno.

El corpus son 20 documentos: unos cientos de fragmentos. Una matriz densa y un
producto matricial alcanzan de sobra, y son exactos; un indice aproximado
(FAISS, HNSW) solo agregaria una fuente de error para ahorrar milisegundos.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from retriever.chunking import Fragmento, trocear
from retriever.config import Config
from retriever.corpus import cargar_corpus
from retriever.encoders import Encoder, crear_encoder


@dataclass(frozen=True)
class Resultado:
    fragmento: Fragmento
    score: float


class Indice:
    """Fragmentos del corpus con su matriz de embeddings."""

    def __init__(self, fragmentos: list[Fragmento], matriz: np.ndarray, encoder: Encoder,
                 cfg: Config) -> None:
        if len(fragmentos) != matriz.shape[0]:
            raise ValueError("la cantidad de fragmentos no coincide con la de vectores")
        self.fragmentos = fragmentos
        self.matriz = matriz
        self.encoder = encoder
        self.cfg = cfg

    @classmethod
    def construir(cls, cfg: Config, encoder: Encoder | None = None,
                  ruta_corpus: str | Path | None = None) -> "Indice":
        """Carga el corpus, lo trocea y embebe cada fragmento."""
        documentos = cargar_corpus(ruta_corpus or cfg.ruta_corpus)
        fragmentos = trocear(documentos, cfg.chunking)
        if not fragmentos:
            raise ValueError("el corpus no produjo ningun fragmento")

        encoder = encoder or crear_encoder(cfg.encoder)
        textos = [f.para_embeber(cfg.chunking.prefijo_metadatos) for f in fragmentos]
        return cls(fragmentos, encoder.codificar_pasajes(textos), encoder, cfg)

    def buscar(self, consulta: str, top_k: int | None = None,
               umbral: float | None = None) -> list[Resultado]:
        """Devuelve los fragmentos mas parecidos, de mayor a menor coseno.

        El umbral es lo que protege la precision: en una pregunta que se contesta
        con un solo fragmento, devolver `top_k` fijo mete k-1 fragmentos sin
        evidencia. Cortar por similitud deja que cada pregunta traiga lo que
        necesita.
        """
        top_k = self.cfg.busqueda.top_k if top_k is None else top_k
        umbral = self.cfg.busqueda.umbral if umbral is None else umbral

        vector = self.encoder.codificar_consultas([consulta])[0]
        scores = self.matriz @ vector          # coseno: los vectores estan normalizados

        # argsort descendente estable: ante empate gana el fragmento mas temprano
        # del corpus, que esta ordenado alfabeticamente -> resultado determinista.
        orden = np.argsort(-scores, kind="stable")[:top_k]
        return [
            Resultado(fragmento=self.fragmentos[i], score=float(scores[i]))
            for i in orden
            if scores[i] >= umbral
        ]

    def __len__(self) -> int:
        return len(self.fragmentos)
