#!/usr/bin/env python3
"""Servidor MCP stdio con las seis herramientas del hospital."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from retriever.config import cargar_config
from retriever.index import Indice
from tools.hospital_api import HospitalAPI
from tools.hospital_tools import DESCRIPCIONES, HerramientasHospital


NOMBRE_SERVIDOR = "hospital-arroyo-claro"
NOMBRES_TOOLS = (
    "buscar_documentos",
    "consultar_camas",
    "consultar_guardia",
    "consultar_turnos",
    "consultar_farmacia",
    "consultar_espera",
)


def crear_servidor(
    indice: Indice | None = None,
    api: HospitalAPI | None = None,
) -> FastMCP:
    """Construye el servidor; las dependencias inyectables facilitan los tests."""
    indice = indice or Indice.construir(cargar_config())
    servicios = HerramientasHospital(indice, api or HospitalAPI())
    servidor = FastMCP(NOMBRE_SERVIDOR)
    for nombre in NOMBRES_TOOLS:
        servidor.tool(name=nombre, description=DESCRIPCIONES[nombre])(
            getattr(servicios, nombre)
        )
    return servidor


def main() -> None:
    """Sirve MCP por stdin/stdout, sin escribir datos ajenos al protocolo."""
    crear_servidor().run(transport="stdio")


if __name__ == "__main__":
    main()
