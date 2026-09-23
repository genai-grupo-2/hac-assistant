"""Recuperador vectorial del Hospital Arroyo Claro (parte 1 de la mision)."""
from recuperador.config import Config, cargar_config
from recuperador.corpus import Documento, cargar_corpus
from recuperador.chunking import Fragmento, trocear
from recuperador.indice import Indice, Resultado

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
