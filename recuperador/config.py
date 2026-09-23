"""Configuracion del recuperador, leida de un YAML.

La consigna pide que la configuracion ganadora quede fija en un archivo, porque
la catedra corre `recuperar.py` tal cual sobre las preguntas de test. Todo
parametro que se toque en un experimento tiene que entrar por aca.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ConfigChunking:
    """Como se corta cada documento en fragmentos."""

    estrategia: str = "estructura"      # "estructura" | "ventana"
    max_palabras: int = 180             # tope duro de un fragmento
    min_palabras: int = 20              # por debajo, se fusiona con el vecino
    tamano: int = 150                   # solo "ventana": palabras por ventana
    solapamiento: int = 40              # solo "ventana": palabras compartidas
    prefijo_metadatos: bool = True      # anteponer "documento > seccion"


@dataclass(frozen=True)
class ConfigBusqueda:
    """Cuantos fragmentos devolver y desde que coseno."""

    top_k: int = 4
    umbral: float = 0.0


@dataclass(frozen=True)
class Config:
    nombre: str = "base"
    corpus: str = "datos/corpus"
    encoder: str = "e5_small"
    chunking: ConfigChunking = field(default_factory=ConfigChunking)
    busqueda: ConfigBusqueda = field(default_factory=ConfigBusqueda)

    @property
    def ruta_corpus(self) -> Path:
        ruta = Path(self.corpus)
        return ruta if ruta.is_absolute() else RAIZ / ruta

    def con(self, **cambios: Any) -> "Config":
        """Copia con parametros pisados. Lo usa el barrido de experimentos."""
        anidados = {"chunking": ConfigChunking, "busqueda": ConfigBusqueda}
        for clave, tipo in anidados.items():
            if clave in cambios and isinstance(cambios[clave], dict):
                cambios[clave] = replace(getattr(self, clave), **cambios[clave])
        return replace(self, **cambios)


def cargar_config(ruta: str | Path | None = None) -> Config:
    """Lee el YAML de configuracion. Sin ruta, usa `config.yaml` de la raiz."""
    ruta = Path(ruta) if ruta else RAIZ / "config.yaml"
    if not ruta.exists():
        return Config()

    crudo: dict[str, Any] = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    return Config(
        nombre=crudo.get("nombre", "base"),
        corpus=crudo.get("corpus", "datos/corpus"),
        encoder=crudo.get("encoder", "e5_small"),
        chunking=ConfigChunking(**(crudo.get("chunking") or {})),
        busqueda=ConfigBusqueda(**(crudo.get("busqueda") or {})),
    )
