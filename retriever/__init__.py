"""Recuperador vectorial del Hospital Arroyo Claro (parte 1 de la mision)."""
from retriever.config import Config, cargar_config
from retriever.corpus import Documento, cargar_corpus
from retriever.chunking import Fragmento, trocear
from retriever.index import Indice, Resultado

__all__ = [
    "Config",
    "cargar_config",
    "Documento",
    "cargar_corpus",
    "Fragmento",
    "trocear",
    "Indice",
    "Resultado",
]
