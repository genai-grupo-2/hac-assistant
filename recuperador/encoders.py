"""Encoders: de texto a vector.

Tres familias, que son las tres filas minimas que pide la consigna:

1. `bert_base` / `bert_multi`: **la linea de base obligatoria**. Un BERT sin
   ajustar para similitud, con el embedding del fragmento calculado como el
   promedio de los vectores de sus tokens en la ultima capa. No fue entrenado
   con un objetivo de similitud, asi que su espacio esta dominado por frecuencia
   y forma, no por significado: es el numero a superar.
2. `minilm`: un sentence-transformer multilingue, entrenado con pares de
   parafrasis, que si tiene un espacio donde el coseno significa algo.
3. `e5_small` / `e5_base`: entrenados con contrastivo asimetrico. Piden los
   prefijos `query: ` y `passage: `, que le avisan al modelo de que lado del par
   esta cada texto. Sin los prefijos rinden bastante peor.

Todos corren en CPU. Los vectores salen normalizados a norma 1, asi el coseno
es un simple producto punto.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

LOTE = 16          # tamano de lote; en CPU subirlo no ayuda mucho
MAX_TOKENS = 512


@runtime_checkable
class Encoder(Protocol):
    """Lo unico que el indice necesita saber de un encoder."""

    nombre: str

    def codificar_pasajes(self, textos: list[str]) -> np.ndarray: ...

    def codificar_consultas(self, textos: list[str]) -> np.ndarray: ...


def normalizar(vectores: np.ndarray) -> np.ndarray:
    """L2 por fila, con guarda para vectores nulos."""
    normas = np.linalg.norm(vectores, axis=-1, keepdims=True)
    return vectores / np.maximum(normas, 1e-12)


@dataclass
class EncoderMeanPooling:
    """BERT crudo + mean pooling de la ultima capa. La linea de base.

    El promedio pondera todos los tokens por igual y descarta el padding via la
    attention mask; usar `[CLS]` en un BERT sin fine-tuning para similitud es
    todavia peor, porque ese vector solo se entreno para la tarea de NSP.
    """

    modelo_id: str
    nombre: str = "bert"

    def __post_init__(self) -> None:
        from transformers import AutoModel, AutoTokenizer  # import perezoso: es caro

        self._tok = AutoTokenizer.from_pretrained(self.modelo_id)
        self._modelo = AutoModel.from_pretrained(self.modelo_id).eval()

    def _codificar(self, textos: list[str]) -> np.ndarray:
        import torch

        vectores = []
        with torch.no_grad():
            for i in range(0, len(textos), LOTE):
                lote = self._tok(
                    textos[i : i + LOTE],
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_tensors="pt",
                )
                ultima = self._modelo(**lote).last_hidden_state
                mascara = lote["attention_mask"].unsqueeze(-1).float()
                promedio = (ultima * mascara).sum(1) / mascara.sum(1).clamp(min=1e-9)
                vectores.append(promedio.numpy())
        return normalizar(np.vstack(vectores))

    def codificar_pasajes(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos)

    def codificar_consultas(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos)


@dataclass
class EncoderSentenceTransformer:
    """Sentence-transformer, con prefijos opcionales por lado del par."""

    modelo_id: str
    nombre: str = "st"
    prefijo_consulta: str = ""
    prefijo_pasaje: str = ""

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer  # import perezoso

        self._modelo = SentenceTransformer(self.modelo_id, device="cpu")

    def _codificar(self, textos: list[str], prefijo: str) -> np.ndarray:
        vectores = self._modelo.encode(
            [prefijo + t for t in textos],
            batch_size=LOTE,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectores, dtype=np.float32)

    def codificar_pasajes(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos, self.prefijo_pasaje)

    def codificar_consultas(self, textos: list[str]) -> np.ndarray:
        return self._codificar(textos, self.prefijo_consulta)


# Catalogo de encoders comparables. La clave es la que va en `config.yaml`.
CATALOGO: dict[str, dict] = {
    # --- linea de base obligatoria ---
    "bert_base": {
        "clase": EncoderMeanPooling,
        "modelo_id": "dccuchile/bert-base-spanish-wwm-cased",
    },
    "bert_multi": {
        "clase": EncoderMeanPooling,
        "modelo_id": "google-bert/bert-base-multilingual-cased",
    },
    # --- entrenados para embeddings de oraciones ---
    "minilm": {
        "clase": EncoderSentenceTransformer,
        "modelo_id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    },
    "e5_small": {
        "clase": EncoderSentenceTransformer,
        "modelo_id": "intfloat/multilingual-e5-small",
        "prefijo_consulta": "query: ",
        "prefijo_pasaje": "passage: ",
    },
    "e5_base": {
        "clase": EncoderSentenceTransformer,
        "modelo_id": "intfloat/multilingual-e5-base",
        "prefijo_consulta": "query: ",
        "prefijo_pasaje": "passage: ",
    },
    "bge_m3": {
        "clase": EncoderSentenceTransformer,
        "modelo_id": "BAAI/bge-m3",
    },
}


def crear_encoder(clave: str) -> Encoder:
    """Instancia el encoder del catalogo. El modelo se descarga la primera vez."""
    if clave not in CATALOGO:
        raise ValueError(
            f"encoder desconocido: {clave!r} "
            f"(opciones: {', '.join(sorted(CATALOGO))})"
        )
    receta = dict(CATALOGO[clave])
    clase = receta.pop("clase")
    return clase(nombre=clave, **receta)
