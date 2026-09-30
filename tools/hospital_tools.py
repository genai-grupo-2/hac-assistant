"""Implementacion compartida de las seis herramientas del hospital."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.tools import StructuredTool

from tools.hospital_api import HospitalAPI


class Buscador(Protocol):
    """Contrato minimo del indice vectorial usado por las tools."""

    def buscar(self, consulta: str) -> list[Any]: ...


DESCRIPCIONES = {
    "buscar_documentos": "Busca en los documentos estables del hospital la informacion normativa o de procedimientos necesaria para responder una consulta. Usala para horarios de visita, requisitos, preparacion de estudios, derechos, acompanamiento y otras reglas del hospital.",
    "consultar_camas": "Consulta en tiempo real cuantas camas totales, ocupadas y libres hay en un sector del hospital. Usala para preguntas sobre disponibilidad de internacion; no inventes el sector si falta.",
    "consultar_guardia": "Consulta que profesionales estan de guardia hoy para una especialidad y sus horarios. Usala para preguntas sobre quien esta de guardia.",
    "consultar_turnos": "Consulta los proximos turnos disponibles para una especialidad. Usala cuando la persona pregunte por fechas u horarios de turnos.",
    "consultar_farmacia": "Consulta stock y fecha de reposicion de un medicamento en la farmacia del hospital. Usala para disponibilidad de medicamentos.",
    "consultar_espera": "Consulta los minutos de espera actuales de la guardia por nivel de triage. Usala para preguntas sobre cuanto se esta esperando.",
}


@dataclass(frozen=True)
class HerramientasHospital:
    """Servicios compartidos por el agente directo y el servidor MCP."""

    indice: Buscador
    api: HospitalAPI

    def buscar_documentos(self, consulta: str) -> str:
        resultados = self.indice.buscar(consulta)
        return json.dumps(
            {"fragmentos": [r.fragmento.texto for r in resultados]},
            ensure_ascii=False,
        )

    def consultar_camas(self, sector: str) -> str:
        return self._json(self.api.get("/camas", {"sector": sector}))

    def consultar_guardia(self, especialidad: str) -> str:
        return self._json(self.api.get("/guardia", {"especialidad": especialidad}))

    def consultar_turnos(self, especialidad: str) -> str:
        return self._json(self.api.get("/turnos", {"especialidad": especialidad}))

    def consultar_farmacia(self, medicamento: str) -> str:
        return self._json(self.api.get("/farmacia", {"medicamento": medicamento}))

    def consultar_espera(self) -> str:
        return self._json(self.api.get("/espera"))

    @staticmethod
    def _json(valor: Any) -> str:
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def crear_tools_langchain(servicios: HerramientasHospital) -> list[StructuredTool]:
    """Adapta las seis funciones compartidas a tools de LangChain."""
    nombres = (
        "buscar_documentos",
        "consultar_camas",
        "consultar_guardia",
        "consultar_turnos",
        "consultar_farmacia",
        "consultar_espera",
    )
    return [
        StructuredTool.from_function(
            getattr(servicios, nombre),
            name=nombre,
            description=DESCRIPCIONES[nombre],
        )
        for nombre in nombres
    ]
