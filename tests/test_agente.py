"""Pruebas offline del ciclo de tool calling de la Parte 2."""
from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from agente import ejecutar_pregunta


class ModeloFalso:
    """Devuelve primero una llamada a tool y después una respuesta final."""

    def __init__(self) -> None:
        self.turno = 0

    def invoke(self, _mensajes):
        self.turno += 1
        if self.turno == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "tool_prueba",
                        "args": {"valor": "dato"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        return AIMessage(content="La respuesta está respaldada por el dato.")


def test_ejecutar_pregunta_conserva_contexto_y_llamada():
    def tool_prueba(valor: str) -> str:
        return f"resultado: {valor}"

    tool = StructuredTool.from_function(tool_prueba, name="tool_prueba", description="tool de prueba")
    salida, log = ejecutar_pregunta(
        {"id": "T01", "pregunta": "¿Cuál es el dato?"},
        ModeloFalso(),
        [tool],
    )

    assert salida["id"] == "T01"
    assert salida["respuesta"] == "La respuesta está respaldada por el dato."
    assert salida["contextos"] == ["resultado: dato"]
    assert salida["herramientas"] == ["tool_prueba"]
    assert log["llamadas"][0]["argumentos"] == {"valor": "dato"}
    assert len(log["modelos"]) == 2
