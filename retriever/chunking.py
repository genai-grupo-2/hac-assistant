"""Troceado de los documentos en fragmentos.

Dos estrategias, porque la metrica las castiga distinto:

- `estructura`: corta por encabezados Markdown. Los documentos del hospital son
  normativos y cada seccion ("Horarios de visita", "Preparacion para una
  ecografia") es una unidad de sentido cerrada, asi que el corte por seccion
  suele dejar la evidencia entera adentro de un solo fragmento: mejor recall
  sin inflar el tamano.
- `ventana`: ventana deslizante de palabras con solapamiento. Es la linea de
  base clasica, agnostica al formato.

En las dos, un fragmento demasiado largo baja la precision (trae ruido) y uno
demasiado corto parte la evidencia en dos. De ahi `max_palabras` / `min_palabras`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from retriever.config import ConfigChunking
from retriever.corpus import Documento

_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class Fragmento:
    texto: str
    doc_id: str
    documento: str        # titulo del documento
    seccion: str          # ruta de encabezados, "Visitas > Terapia intensiva"

    def para_embeber(self, prefijo_metadatos: bool = True) -> str:
        """Texto que se le pasa al encoder.

        Anteponer el titulo del documento y de la seccion le da contexto a un
        fragmento que por si solo puede ser ambiguo ("de 14 a 16"), a costa de
        unas pocas palabras de ruido.
        """
        if not prefijo_metadatos:
            return self.texto
        cabecera = " > ".join(p for p in (self.documento, self.seccion) if p)
        return f"{cabecera}\n\n{self.texto}" if cabecera else self.texto


def _palabras(texto: str) -> list[str]:
    return texto.split()


def _partir_largo(texto: str, max_palabras: int) -> list[str]:
    """Parte un texto largo respetando limites de parrafo cuando se puede."""
    if len(_palabras(texto)) <= max_palabras:
        return [texto]

    partes: list[str] = []
    actual: list[str] = []
    n_actual = 0
    for parrafo in texto.split("\n\n"):
        n_parrafo = len(_palabras(parrafo))
        if n_parrafo > max_palabras:
            # Un solo parrafo mas largo que el tope (una tabla, por ejemplo):
            # se corta por palabras, no hay limite natural al que agarrarse.
            if actual:
                partes.append("\n\n".join(actual))
                actual, n_actual = [], 0
            palabras = _palabras(parrafo)
            for i in range(0, len(palabras), max_palabras):
                partes.append(" ".join(palabras[i : i + max_palabras]))
            continue
        if n_actual + n_parrafo > max_palabras and actual:
            partes.append("\n\n".join(actual))
            actual, n_actual = [], 0
        actual.append(parrafo)
        n_actual += n_parrafo
    if actual:
        partes.append("\n\n".join(actual))
    return partes


def _fusionar_cortos(fragmentos: list[Fragmento], min_palabras: int) -> list[Fragmento]:
    """Pega un fragmento muy corto al anterior del mismo documento.

    Un encabezado suelto o una linea de dos palabras no es recuperable por si
    misma y ademas ensucia la precision si sale elegida.
    """
    salida: list[Fragmento] = []
    for frag in fragmentos:
        if (
            salida
            and len(_palabras(frag.texto)) < min_palabras
            and salida[-1].doc_id == frag.doc_id
        ):
            previo = salida[-1]
            salida[-1] = Fragmento(
                texto=f"{previo.texto}\n\n{frag.texto}",
                doc_id=previo.doc_id,
                documento=previo.documento,
                seccion=previo.seccion,
            )
        else:
            salida.append(frag)
    return salida


def _por_estructura(doc: Documento, cfg: ConfigChunking) -> list[Fragmento]:
    pila: list[str] = []          # ruta de encabezados vigente
    cuerpo: list[str] = []
    fragmentos: list[Fragmento] = []

    def cerrar() -> None:
        texto = "\n".join(cuerpo).strip()
        if not texto:
            return
        # pila[0] es el titulo del documento; la seccion es lo que sigue.
        seccion = " > ".join(pila[1:]) if len(pila) > 1 else ""
        for parte in _partir_largo(texto, cfg.max_palabras):
            fragmentos.append(
                Fragmento(
                    texto=parte,
                    doc_id=doc.doc_id,
                    documento=doc.titulo,
                    seccion=seccion,
                )
            )

    for linea in doc.texto.splitlines():
        encabezado = _ENCABEZADO.match(linea)
        if encabezado:
            cerrar()
            cuerpo = []
            nivel, titulo = len(encabezado.group(1)), encabezado.group(2).strip()
            pila = pila[: nivel - 1] + [titulo]
        else:
            cuerpo.append(linea)
    cerrar()

    return _fusionar_cortos(fragmentos, cfg.min_palabras)


def _por_ventana(doc: Documento, cfg: ConfigChunking) -> list[Fragmento]:
    if cfg.solapamiento >= cfg.tamano:
        raise ValueError("el solapamiento tiene que ser menor que el tamano de ventana")

    palabras = _palabras(doc.texto)
    paso = cfg.tamano - cfg.solapamiento
    fragmentos = []
    for inicio in range(0, max(len(palabras), 1), paso):
        ventana = palabras[inicio : inicio + cfg.tamano]
        if not ventana:
            break
        fragmentos.append(
            Fragmento(
                texto=" ".join(ventana),
                doc_id=doc.doc_id,
                documento=doc.titulo,
                seccion="",
            )
        )
        if inicio + cfg.tamano >= len(palabras):
            break
    return fragmentos


def trocear(documentos: list[Documento], cfg: ConfigChunking) -> list[Fragmento]:
    """Aplica la estrategia configurada a todos los documentos."""
    estrategias = {"estructura": _por_estructura, "ventana": _por_ventana}
    if cfg.estrategia not in estrategias:
        raise ValueError(
            f"estrategia de chunking desconocida: {cfg.estrategia!r} "
            f"(opciones: {', '.join(sorted(estrategias))})"
        )
    partir = estrategias[cfg.estrategia]
    return [frag for doc in documentos for frag in partir(doc, cfg)]
