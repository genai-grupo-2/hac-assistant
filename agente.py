#!/usr/bin/env python3
"""Parte 2: agente LangChain con recuperador y API del hospital.

Uso:
    python agente.py --preguntas datos/preguntas_agente_dev.jsonl --salida respuestas.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from retriever.config import cargar_config
from retriever.index import Indice
from tools.hospital_api import crear_tools_api


MODELO = "deepseek/deepseek-v4-flash-0731"
BASE_URL = "https://openrouter.ai/api/v1"

SYSTEM_PROMPT = """Sos el asistente del Hospital Provincial Arroyo Claro.
Respondé en español, de forma clara y breve.

Tenés dos fuentes y debés usar tools antes de responder:
- buscar_documentos contiene normas y procedimientos estables del hospital.
- las cinco tools de la API contienen el estado actual de camas, guardia,
  turnos, farmacia y espera.

Para una pregunta que combine ambas fuentes, llamá a todas las tools necesarias.
No inventes datos ni completes información ausente con conocimiento general.
Basá cada afirmación en los resultados recibidos. Si una tool devuelve un error,
explicalo y no ocultes la falta de información. No menciones nombres internos
de tools ni el proceso de razonamiento en la respuesta final.
"""


def leer_preguntas(ruta: str | Path) -> list[dict[str, Any]]:
    """Lee preguntas JSONL preservando su orden."""
    return [
        json.loads(line)
        for line in Path(ruta).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def texto_mensaje(contenido: Any) -> str:
    """Convierte el contenido de un mensaje LangChain a texto."""
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict) and isinstance(bloque.get("text"), str):
                partes.append(bloque["text"])
        return "".join(partes)
    return str(contenido)


def json_seguro(valor: Any) -> Any:
    """Prepara metadatos de LangChain para escribirlos en el log."""
    try:
        json.dumps(valor)
        return valor
    except TypeError:
        return str(valor)


def usage_de(mensaje: AIMessage) -> dict[str, Any]:
    """Extrae usage y costo disponibles en la respuesta del proveedor."""
    uso = dict(getattr(mensaje, "usage_metadata", None) or {})
    metadata = dict(getattr(mensaje, "response_metadata", None) or {})
    token_usage = metadata.get("token_usage") or metadata.get("usage") or {}
    if isinstance(token_usage, dict):
        for origen, destino in (
            ("prompt_tokens", "input_tokens"),
            ("completion_tokens", "output_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            if destino not in uso and origen in token_usage:
                uso[destino] = token_usage[origen]
    costo = metadata.get("cost")
    if costo is None and isinstance(token_usage, dict):
        costo = token_usage.get("cost")
    if costo is not None:
        uso["cost"] = costo
    return {"usage": json_seguro(uso), "response_metadata": json_seguro(metadata)}


def crear_tools(indice: Indice) -> list[StructuredTool]:
    """Crea las seis tools exigidas por la consigna."""
    def buscar_documentos(consulta: str) -> str:
        resultados = indice.buscar(consulta)
        return json.dumps(
            {"fragmentos": [r.fragmento.texto for r in resultados]},
            ensure_ascii=False,
        )

    documental = StructuredTool.from_function(
        buscar_documentos,
        name="buscar_documentos",
        description="Busca en los documentos estables del hospital la información normativa o de procedimientos necesaria para responder una consulta. Usala para horarios de visita, requisitos, preparación de estudios, derechos, acompañamiento y otras reglas del hospital.",
    )
    return [documental, *crear_tools_api()]


def ejecutar_pregunta(
    pregunta: dict[str, Any],
    modelo: Any,
    tools: list[StructuredTool],
    max_turnos: int = 8,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ejecuta el ciclo de tool calling y devuelve respuesta más log."""
    por_nombre = {tool.name: tool for tool in tools}
    mensajes: list[Any] = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=pregunta["pregunta"]),
    ]
    contextos: list[str] = []
    herramientas: list[str] = []
    llamadas: list[dict[str, Any]] = []
    modelos: list[dict[str, Any]] = []
    respuesta = ""

    for turno in range(1, max_turnos + 1):
        mensaje = modelo.invoke(mensajes)
        modelos.append({"turno": turno, **usage_de(mensaje)})
        mensajes.append(mensaje)
        tool_calls = list(getattr(mensaje, "tool_calls", None) or [])
        if not tool_calls:
            respuesta = texto_mensaje(mensaje.content).strip()
            break

        for llamada in tool_calls:
            nombre = llamada.get("name", "")
            argumentos = llamada.get("args") or {}
            herramientas.append(nombre)
            tool = por_nombre.get(nombre)
            if tool is None:
                resultado = json.dumps({"error": f"tool inexistente: {nombre}"}, ensure_ascii=False)
            else:
                try:
                    resultado = str(tool.invoke(argumentos))
                except Exception as error:  # el agente debe poder informar el error
                    resultado = json.dumps({"error": str(error)}, ensure_ascii=False)
            contextos.append(resultado)
            llamadas.append({"turno": turno, "tool": nombre, "argumentos": json_seguro(argumentos), "resultado": resultado})
            mensajes.append(
                ToolMessage(
                    content=resultado,
                    tool_call_id=llamada.get("id", f"tool-{turno}-{len(llamadas)}"),
                    name=nombre,
                )
            )
    else:
        respuesta = "No pude completar la consulta dentro del límite de pasos."

    salida = {
        "id": pregunta.get("id"),
        "respuesta": respuesta,
        "contextos": contextos,
        "herramientas": herramientas,
    }
    registro = {
        "id": pregunta.get("id"),
        "pregunta": pregunta.get("pregunta"),
        "llamadas": llamadas,
        "respuesta": respuesta,
        "modelos": modelos,
    }
    return salida, registro


def escribir_jsonl(filas: list[dict[str, Any]], ruta: str | Path) -> None:
    """Escribe una salida JSONL en el orden original."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as archivo:
        for fila in filas:
            archivo.write(json.dumps(fila, ensure_ascii=False) + "\n")


def escribir_log(registros: list[dict[str, Any]], ruta_salida: str | Path) -> Path:
    """Escribe el log Markdown obligatorio de la corrida."""
    salida = Path(ruta_salida)
    log = salida.with_suffix(".log.md")
    total_costo = 0.0
    lineas = [
        "# Log de agente",
        "",
        f"- Modelo: {MODELO}",
        f"- Base URL: {BASE_URL}",
        f"- Inicio: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    for registro in registros:
        lineas.extend([f"## {registro['id']}: {registro['pregunta']}", ""])
        lineas.append("### Llamadas a herramientas")
        lineas.append("")
        if registro["llamadas"]:
            for llamada in registro["llamadas"]:
                lineas.extend(
                    [
                        f"- Tool: `{llamada['tool']}`",
                        f"  - Argumentos: `{json.dumps(llamada['argumentos'], ensure_ascii=False)}`",
                        f"  - Resultado: `{llamada['resultado']}`",
                    ]
                )
        else:
            lineas.append("- No hubo llamadas a herramientas.")
        lineas.extend(["", "### Respuesta", "", registro["respuesta"], "", "### Usage por llamada al modelo", ""])
        for modelo in registro["modelos"]:
            uso = modelo.get("usage") or {}
            if isinstance(uso, dict) and isinstance(uso.get("cost"), (int, float)):
                total_costo += float(uso["cost"])
            lineas.extend(
                [
                    f"- Turno {modelo['turno']}: `{json.dumps(uso, ensure_ascii=False)}`",
                    f"  - Metadata: `{json.dumps(modelo.get('response_metadata', {}), ensure_ascii=False)}`",
                ]
            )
        lineas.extend(["", "---", ""])
    lineas.extend([f"Costo acumulado reportado por el proveedor: USD {total_costo:.8f}", ""])
    log.write_text("\n".join(lineas), encoding="utf-8")
    return log


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preguntas", required=True)
    parser.add_argument("--salida", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("falta la variable OPENROUTER_API_KEY", file=sys.stderr)
        return 2

    cfg = cargar_config()
    indice = Indice.construir(cfg)
    tools = crear_tools(indice)
    modelo = ChatOpenAI(
        model=MODELO,
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url=BASE_URL,
        temperature=0,
    ).bind_tools(tools)

    salidas: list[dict[str, Any]] = []
    registros: list[dict[str, Any]] = []
    for pregunta in leer_preguntas(args.preguntas):
        print(f"[agente] procesando {pregunta.get('id')}", file=sys.stderr)
        salida, registro = ejecutar_pregunta(pregunta, modelo, tools)
        salidas.append(salida)
        registros.append(registro)

    escribir_jsonl(salidas, args.salida)
    log = escribir_log(registros, args.salida)
    print(f"[agente] {len(salidas)} preguntas -> {args.salida}", file=sys.stderr)
    print(f"[agente] log -> {log}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
