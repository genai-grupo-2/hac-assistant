"""Pruebas offline de la Parte 3 (sin API, modelos ni red)."""
from __future__ import annotations

import asyncio
import json

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from agente import ejecutar_pregunta_async
from tools.hospital_tools import HerramientasHospital, crear_tools_langchain


class IndiceFalso:
    def buscar(self, consulta: str):
        fragmento = type("Fragmento", (), {"texto": f"documento: {consulta}"})()
        return [type("Resultado", (), {"fragmento": fragmento})()]


class APIFalsa:
    def get(self, ruta: str, parametros=None):
        return {"ruta": ruta, "parametros": parametros or {}}


class ModeloFalsoAsync:
    def __init__(self) -> None:
        self.turno = 0

    async def ainvoke(self, _mensajes):
        self.turno += 1
        if self.turno == 1:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "tool_async",
                    "args": {"valor": "dato"},
                    "id": "call-async",
                    "type": "tool_call",
                }],
            )
        return AIMessage(content="Respuesta obtenida por MCP.")


def test_herramientas_compartidas_conservan_los_seis_nombres():
    servicios = HerramientasHospital(IndiceFalso(), APIFalsa())
    tools = crear_tools_langchain(servicios)
    assert [tool.name for tool in tools] == [
        "buscar_documentos",
        "consultar_camas",
        "consultar_guardia",
        "consultar_turnos",
        "consultar_farmacia",
        "consultar_espera",
    ]


def test_herramientas_compartidas_delegan_en_las_fuentes():
    servicios = HerramientasHospital(IndiceFalso(), APIFalsa())
    assert json.loads(servicios.buscar_documentos("visitas")) == {
        "fragmentos": ["documento: visitas"]
    }
    assert json.loads(servicios.consultar_camas("pediatria")) == {
        "parametros": {"sector": "pediatria"},
        "ruta": "/camas",
    }
    assert json.loads(servicios.consultar_espera()) == {
        "parametros": {},
        "ruta": "/espera",
    }


def test_ciclo_async_conserva_contexto_y_llamada():
    async def tool_async(valor: str) -> str:
        return f"resultado MCP: {valor}"

    tool = StructuredTool.from_function(
        coroutine=tool_async,
        name="tool_async",
        description="tool MCP de prueba",
    )
    salida, log = asyncio.run(
        ejecutar_pregunta_async(
            {"id": "M01", "pregunta": "¿Cuál es el dato?"},
            ModeloFalsoAsync(),
            [tool],
        )
    )

    assert salida["respuesta"] == "Respuesta obtenida por MCP."
    assert salida["contextos"] == ["resultado MCP: dato"]
    assert salida["herramientas"] == ["tool_async"]
    assert log["llamadas"][0]["argumentos"] == {"valor": "dato"}
