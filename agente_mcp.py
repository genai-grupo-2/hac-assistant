#!/usr/bin/env python3
"""Parte 3: agente LangChain que descubre y usa tools de un servidor MCP."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI

from agente import (
    BASE_URL,
    MODELO,
    cargar_env_local,
    escribir_jsonl,
    escribir_log,
    ejecutar_pregunta_async,
    leer_preguntas,
)
from servidor_mcp import NOMBRES_TOOLS


RAIZ = Path(__file__).resolve().parent
SERVIDOR = RAIZ / "servidor_mcp.py"


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preguntas", required=True)
    parser.add_argument("--salida", required=True)
    return parser.parse_args(argv)


def conexion_mcp() -> dict[str, dict[str, object]]:
    """Configura el proceso stdio usando el mismo interprete del cliente."""
    return {
        "hospital": {
            "command": sys.executable,
            "args": [str(SERVIDOR)],
            "transport": "stdio",
        }
    }


async def ejecutar(args: argparse.Namespace) -> int:
    """Descubre las tools por MCP y procesa las preguntas en una sesion."""
    cliente = MultiServerMCPClient(conexion_mcp())
    async with cliente.session("hospital") as sesion:
        tools = await load_mcp_tools(sesion)
        descubiertas = {tool.name for tool in tools}
        faltantes = set(NOMBRES_TOOLS) - descubiertas
        if faltantes:
            nombres = ", ".join(sorted(faltantes))
            raise RuntimeError(f"el servidor MCP no publico estas tools: {nombres}")

        modelo = ChatOpenAI(
            model=MODELO,
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=BASE_URL,
            temperature=0,
        ).bind_tools(tools)

        salidas = []
        registros = []
        for pregunta in leer_preguntas(args.preguntas):
            print(f"[agente_mcp] procesando {pregunta.get('id')}", file=sys.stderr)
            salida, registro = await ejecutar_pregunta_async(pregunta, modelo, tools)
            salidas.append(salida)
            registros.append(registro)

    escribir_jsonl(salidas, args.salida)
    log = escribir_log(registros, args.salida)
    print(f"[agente_mcp] {len(salidas)} preguntas -> {args.salida}", file=sys.stderr)
    print(f"[agente_mcp] log -> {log}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)
    cargar_env_local(RAIZ / ".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("falta la variable OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    return asyncio.run(ejecutar(args))


if __name__ == "__main__":
    raise SystemExit(main())
