"""Carga del corpus del hospital: los .md de `datos/corpus/`."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Documento:
    doc_id: str      # nombre del archivo sin extension
    titulo: str      # primer encabezado `#`, o el doc_id si no hay
    texto: str


def _titulo_de(texto: str, por_defecto: str) -> str:
    for linea in texto.splitlines():
        if linea.startswith("# "):
            return linea[2:].strip()
    return por_defecto.replace("_", " ").replace("-", " ").strip()


def cargar_corpus(directorio: str | Path) -> list[Documento]:
    """Lee los .md del directorio, ordenados por nombre.

    El orden alfabetico es deliberado: dos corridas tienen que producir los
    mismos fragmentos en el mismo orden, o los experimentos no son comparables.
    """
    directorio = Path(directorio)
    if not directorio.is_dir():
        raise FileNotFoundError(
            f"No existe el directorio del corpus: {directorio}. "
            "Es el material que entrega la catedra en datos/corpus/."
        )

    documentos = []
    for ruta in sorted(directorio.glob("*.md")):
        texto = ruta.read_text(encoding="utf-8")
        # Normaliza saltos de linea y colapsa lineas en blanco de mas, para que
        # el troceado por parrafos no dependa del formateo del archivo.
        texto = re.sub(r"\n{3,}", "\n\n", texto.replace("\r\n", "\n")).strip()
        documentos.append(
            Documento(doc_id=ruta.stem, titulo=_titulo_de(texto, ruta.stem), texto=texto)
        )
    return documentos
