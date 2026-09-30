"""Cliente HTTP y tools LangChain para la API del hospital."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from langchain_core.tools import StructuredTool


@dataclass(frozen=True)
class HospitalAPI:
    """Cliente pequeño y determinista para la API local del hospital."""

    base_url: str = "http://localhost:8765"
    timeout: float = 15.0

    def get(self, ruta: str, parametros: dict[str, str] | None = None) -> dict[str, Any]:
        """Hace un GET y devuelve el JSON, incluidos errores HTTP de la API."""
        query = urlencode(parametros or {})
        url = f"{self.base_url.rstrip('/')}{ruta}"
        if query:
            url = f"{url}?{query}"
        try:
            with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=self.timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except HTTPError as error:
            cuerpo = error.read().decode("utf-8", errors="replace")
            try:
                return json.loads(cuerpo)
            except json.JSONDecodeError:
                return {"error": f"HTTP {error.code}: {cuerpo}"}
        except URLError as error:
            return {"error": f"no se pudo conectar con la API del hospital: {error.reason}"}
        except TimeoutError:
            return {"error": "la API del hospital agotó el tiempo de espera"}


def _json(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True)


def crear_tools_api(cliente: HospitalAPI | None = None) -> list[StructuredTool]:
    """Crea las cinco tools que consultan el estado vivo del hospital."""
    api = cliente or HospitalAPI()

    def consultar_camas(sector: str) -> str:
        return _json(api.get("/camas", {"sector": sector}))

    def consultar_guardia(especialidad: str) -> str:
        return _json(api.get("/guardia", {"especialidad": especialidad}))

    def consultar_turnos(especialidad: str) -> str:
        return _json(api.get("/turnos", {"especialidad": especialidad}))

    def consultar_farmacia(medicamento: str) -> str:
        return _json(api.get("/farmacia", {"medicamento": medicamento}))

    def consultar_espera() -> str:
        return _json(api.get("/espera"))

    return [
        StructuredTool.from_function(
            consultar_camas,
            name="consultar_camas",
            description="Consulta en tiempo real cuántas camas totales, ocupadas y libres hay en un sector del hospital. Usala para preguntas sobre disponibilidad de internación; no inventes el sector si falta.",
        ),
        StructuredTool.from_function(
            consultar_guardia,
            name="consultar_guardia",
            description="Consulta qué profesionales están de guardia hoy para una especialidad y sus horarios. Usala para preguntas sobre quién está de guardia.",
        ),
        StructuredTool.from_function(
            consultar_turnos,
            name="consultar_turnos",
            description="Consulta los próximos turnos disponibles para una especialidad. Usala cuando la persona pregunte por fechas u horarios de turnos.",
        ),
        StructuredTool.from_function(
            consultar_farmacia,
            name="consultar_farmacia",
            description="Consulta stock y fecha de reposición de un medicamento en la farmacia del hospital. Usala para disponibilidad de medicamentos.",
        ),
        StructuredTool.from_function(
            consultar_espera,
            name="consultar_espera",
            description="Consulta los minutos de espera actuales de la guardia por nivel de triage. Usala para preguntas sobre cuánto se está esperando.",
        ),
    ]
