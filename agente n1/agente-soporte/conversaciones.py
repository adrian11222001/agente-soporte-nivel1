"""
conversaciones.py
Persistencia de conversaciones y mensajes en MySQL. Cada conversación
pertenece a un usuario y contiene su propio hilo de mensajes, igual
que las "pestañas" de conversación de ChatGPT o Claude.
"""

import json
import uuid

from db import get_conn


def crear_conversacion(usuario_id: int, titulo: str = "Nueva conversación") -> str:
    conversacion_id = str(uuid.uuid4())
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversaciones (conversacion_id, usuario_id, titulo) VALUES (%s, %s, %s)",
            (conversacion_id, usuario_id, titulo),
        )
        conn.commit()
        return conversacion_id
    finally:
        conn.close()


def listar_conversaciones(usuario_id: int) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT conversacion_id, titulo, fecha_creacion, ultima_actividad "
            "FROM conversaciones WHERE usuario_id = %s ORDER BY ultima_actividad DESC",
            (usuario_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def es_dueno(conversacion_id: str, usuario_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM conversaciones WHERE conversacion_id = %s AND usuario_id = %s",
            (conversacion_id, usuario_id),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def guardar_mensaje(conversacion_id: str, rol: str, contenido, herramienta: str | None = None) -> None:
    """
    rol: 'user' | 'assistant' | 'function_call' | 'function_call_output'
    contenido: string para user/assistant, o el dict/objeto completo del
               evento de la Responses API para function_call/function_call_output
               (se serializa a JSON).
    """
    if not isinstance(contenido, str):
        contenido = json.dumps(contenido, ensure_ascii=False)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mensajes (conversacion_id, rol, contenido, herramienta) "
            "VALUES (%s, %s, %s, %s)",
            (conversacion_id, rol, contenido, herramienta),
        )
        cur.execute(
            "UPDATE conversaciones SET ultima_actividad = NOW() WHERE conversacion_id = %s",
            (conversacion_id,),
        )
        conn.commit()
    finally:
        conn.close()


def obtener_historial_para_agente(conversacion_id: str) -> list[dict]:
    """Reconstruye el historial en el formato que espera agent.responder()."""
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT rol, contenido FROM mensajes WHERE conversacion_id = %s ORDER BY mensaje_id",
            (conversacion_id,),
        )
        filas = cur.fetchall()
    finally:
        conn.close()

    historial = []
    for fila in filas:
        if fila["rol"] in ("user", "assistant"):
            historial.append({"role": fila["rol"], "content": fila["contenido"]})
        else:
            historial.append(json.loads(fila["contenido"]))
    return historial


def obtener_mensajes_para_ui(conversacion_id: str) -> list[dict]:
    """Solo los mensajes visibles (usuario/asistente), para pintar el chat al abrir una conversación."""
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT rol, contenido, fecha FROM mensajes "
            "WHERE conversacion_id = %s AND rol IN ('user','assistant') "
            "ORDER BY mensaje_id",
            (conversacion_id,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def actualizar_titulo(conversacion_id: str, titulo: str) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE conversaciones SET titulo = %s WHERE conversacion_id = %s",
            (titulo[:200], conversacion_id),
        )
        conn.commit()
    finally:
        conn.close()


def eliminar_conversacion(conversacion_id: str, usuario_id: int) -> bool:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM conversaciones WHERE conversacion_id = %s AND usuario_id = %s",
            (conversacion_id, usuario_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
