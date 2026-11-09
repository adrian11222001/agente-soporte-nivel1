"""
agent.py
Núcleo del Agente Inteligente de IA (sección 1.4.2 / 1.8 / 1.10 del informe).

Usa la Responses API de OpenAI con function calling (tools) para que el modelo
pueda decidir cuándo ejecutar crear_ticket(), consultar_ticket(), etc.

Cambio respecto a la versión anterior: `usuario_id` ya NO lo escribe el usuario
en el chat ni lo inventa el modelo — viene del login (JWT) y se inyecta aquí
mismo antes de ejecutar la herramienta.
"""

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

import tools

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")

client = OpenAI()

SYSTEM_PROMPT = """Eres el Agente Inteligente de IA para Automatización y Resolución de
Incidencias de Soporte Técnico de Nivel 1 de la organización.

Tu función:
1. Analizar la solicitud del usuario e identificar el tipo de incidencia.
2. Hacer preguntas si falta información antes de actuar.
3. Consultar tu conocimiento para determinar si la incidencia puede resolverse en Nivel 1.
4. Ejecutar la herramienta adecuada cuando corresponda.
5. Si la incidencia supera tu alcance, crear/actualizar el ticket y escalarlo a Nivel 2.
6. Informar siempre al usuario el resultado de la operación, con el ticket_id si aplica.

Reglas (guardrails) — el agente PUEDE:
- Crear, consultar y actualizar tickets.
- Escalar incidencias a Nivel 2.
- Ejecutar diagnósticos básicos.
- Ejecutar el procedimiento autorizado de restablecimiento de credenciales.

El agente NO PUEDE, bajo ninguna circunstancia:
- Ejecutar comandos arbitrarios o acciones no definidas como herramienta.
- Eliminar usuarios o información.
- Modificar configuraciones o sistemas críticos.
- Acceder a información no relacionada con la incidencia reportada.
- Omitir la validación de identidad antes de restablecer una credencial.

El usuario que te escribe ya está autenticado en el sistema, así que nunca le
pidas su usuario_id: ya lo tienes disponible internamente.

Para restablecer_credencial: pide al usuario que confirme el correo registrado
de su cuenta y pásalo tal cual en el parámetro correo_confirmado. Tú NO decides
si el correo es correcto — el sistema lo compara automáticamente contra la base
de datos y rechaza la operación si no coincide. Nunca inventes ni asumas el
correo del usuario: solo usa exactamente lo que él escribió en el chat.

Sé breve, claro y profesional. No inventes estados de tickets ni resultados de
diagnóstico: siempre usa las herramientas para obtener esos datos.
"""

# Nota: "usuario_id" se quitó de los parámetros que declara el modelo;
# se inyecta automáticamente en _run_tool() a partir del usuario autenticado.
TOOLS = [
    {
        "type": "function",
        "name": "crear_ticket",
        "description": "Crea una nueva incidencia cuando el problema no puede resolverse de inmediato.",
        "parameters": {
            "type": "object",
            "properties": {
                "descripcion": {"type": "string", "description": "Descripción del problema."},
                "categoria": {"type": "string", "description": "Categoría de la incidencia, p. ej. Conectividad, Hardware, Software."},
                "prioridad": {"type": "string", "enum": ["Baja", "Media", "Alta"]},
            },
            "required": ["descripcion"],
        },
    },
    {
        "type": "function",
        "name": "consultar_ticket",
        "description": "Consulta el estado actual de un ticket existente.",
        "parameters": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string"}},
            "required": ["ticket_id"],
        },
    },
    {
        "type": "function",
        "name": "actualizar_ticket",
        "description": "Agrega nueva información a un ticket existente (p. ej. el usuario ya probó algo).",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "nueva_informacion": {"type": "string"},
            },
            "required": ["ticket_id", "nueva_informacion"],
        },
    },
    {
        "type": "function",
        "name": "escalar_ticket",
        "description": "Deriva una incidencia a Nivel 2 cuando supera el alcance de Nivel 1.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "motivo": {"type": "string"},
            },
            "required": ["ticket_id", "motivo"],
        },
    },
    {
        "type": "function",
        "name": "restablecer_credencial",
        "description": (
            "Restablece la contraseña de LOGIN de la plataforma para la cuenta autenticada. "
            "El sistema verifica automáticamente que el correo indicado coincida con el registrado; "
            "si no coincide, rechaza la operación sin hacer ningún cambio."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "correo_confirmado": {
                    "type": "string",
                    "description": "Correo que el usuario escribió en el chat para confirmar su identidad, tal cual lo escribió.",
                },
            },
            "required": ["correo_confirmado"],
        },
    },
    {
        "type": "function",
        "name": "diagnosticar_equipo",
        "description": "Ejecuta comprobaciones técnicas básicas: conectividad, memoria, espacio disponible.",
        "parameters": {"type": "object", "properties": {}},
    },
]

# Herramientas que necesitan el usuario_id autenticado inyectado automáticamente
_REQUIERE_USUARIO_ID = {"crear_ticket", "restablecer_credencial", "diagnosticar_equipo"}

TOOL_IMPL = {
    "crear_ticket": tools.crear_ticket,
    "consultar_ticket": tools.consultar_ticket,
    "actualizar_ticket": tools.actualizar_ticket,
    "escalar_ticket": tools.escalar_ticket,
    "restablecer_credencial": tools.restablecer_credencial,
    "diagnosticar_equipo": tools.diagnosticar_equipo,
}


def _run_tool(name: str, arguments: dict, usuario_id: int) -> dict:
    fn = TOOL_IMPL.get(name)
    if not fn:
        return {"error": f"Herramienta desconocida: {name}"}
    if name in _REQUIERE_USUARIO_ID:
        arguments = {**arguments, "usuario_id": usuario_id}

    print(f"\n[ACCIÓN EJECUTADA] {name}({arguments})")  # evidencia visible en consola para la demo
    try:
        resultado = fn(**arguments)
        print(f"[RESULTADO] {resultado}\n")
        return resultado
    except Exception as e:  # nunca dejar que un error de una tool tumbe la conversación
        print(f"[ERROR EN LA ACCIÓN] {e}\n")
        return {"error": str(e)}


def responder(historial: list[dict], mensaje_usuario: str, usuario_id: int) -> tuple[str, list[dict]]:
    """
    historial: lista de turnos previos en formato Responses API (reconstruida
               desde MySQL por conversaciones.obtener_historial_para_agente()).
    usuario_id: id numérico del usuario autenticado (del JWT), usado para
                ligar tickets/auditoría/diagnósticos a la persona correcta.
    Devuelve (texto_de_respuesta, nuevo_historial_actualizado)
    """
    historial = historial + [{"role": "user", "content": mensaje_usuario}]

    for _ in range(8):  # límite de seguridad para evitar loops infinitos
        response = client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=historial,
            tools=TOOLS,
        )

        tool_calls = [item for item in response.output if item.type == "function_call"]

        if not tool_calls:
            texto = response.output_text
            historial.append({"role": "assistant", "content": texto})
            return texto, historial

        for call in response.output:
            if call.type == "function_call":
                # Solo estos campos son válidos para reenviar como 'input' en el
                # siguiente turno. 'status' e 'id' son de solo lectura y la API
                # los rechaza con "Unknown parameter" si se los reenvías.
                historial.append({
                    "type": "function_call",
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": call.arguments,
                })
            # Otros tipos de item (p. ej. "reasoning") se descartan del historial:
            # no son necesarios para mantener el contexto de la conversación
            # y algunos tampoco son válidos como 'input' en el siguiente turno.

        for call in tool_calls:
            args = json.loads(call.arguments or "{}")
            resultado = _run_tool(call.name, args, usuario_id)
            historial.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(resultado, ensure_ascii=False),
            })

    return ("No fue posible completar la solicitud tras varios intentos. "
            "El caso será derivado a un agente humano."), historial
