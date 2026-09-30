# Verificación con MCP Inspector

Verificación realizada el 30 de septiembre de 2026 con MCP Inspector 2.8.0,
servidor `hospital-arroyo-claro`, transporte stdio y protocolo MCP 2025-11-25.

Comando utilizado:

```powershell
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe servidor_mcp.py
```

El Inspector ejecutó `tools/list` y descubrió las seis herramientas esperadas.
Después se llamó manualmente a cada una desde la pestaña **Tools**:

| Herramienta | Argumento de prueba | Resultado observado |
|---|---|---|
| `buscar_documentos` | `consulta="horario de visitas en sala general"` | fragmento con visitas de 16:00 a 20:00 |
| `consultar_camas` | `sector="pediatria"` | 7 libres, 17 ocupadas, 24 totales |
| `consultar_guardia` | `especialidad="cardiologia"` | dos profesionales y sus horarios |
| `consultar_turnos` | `especialidad="cardiologia"` | tres próximos turnos |
| `consultar_farmacia` | `medicamento="amoxicilina 500 mg"` | respuesta JSON de stock |
| `consultar_espera` | sin argumentos | espera por los cinco niveles de triage |

Todas las llamadas aparecieron como `tools/call` con estado `OK` en el panel de
protocolo. Las capturas PNG exigidas por la consigna todavía deben guardarse en
este directorio.
