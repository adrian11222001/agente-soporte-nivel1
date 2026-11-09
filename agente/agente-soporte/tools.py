"""
tools.py (versión MySQL)
Implementación de las 6 herramientas del agente, ahora persistidas en MySQL
en vez de SQLite, para que tickets y auditoría queden ligados a usuarios reales.

    crear_ticket()
    consultar_ticket()
    actualizar_ticket()
    escalar_ticket()
    restablecer_credencial()
    diagnosticar_equipo()
"""

import os
import random
import smtplib
import string
from email.mime.text import MIMEText

from db import get_conn
from auth import hash_password


def _new_id(prefix, n=6):
    return f"{prefix}-{''.join(random.choices(string.digits, k=n))}"


def _log(usuario_id, ticket_id, accion, herramienta, resultado):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO auditoria (id_accion, usuario_id, ticket_id, accion, herramienta, resultado) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (_new_id("ACT"), usuario_id, ticket_id, accion, herramienta, resultado),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------
# Las 6 herramientas del agente
# usuario_id ahora es el INT real de la tabla `usuarios` (viene del JWT),
# no un string libre que escribía el usuario en el chat.
# ---------------------------------------------------------------------

def crear_ticket(usuario_id: int, descripcion: str, categoria: str = "General",
                  prioridad: str = "Media") -> dict:
    ticket_id = _new_id("INC")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tickets (ticket_id, usuario_id, descripcion, categoria, prioridad, "
            "estado, nivel, responsable) VALUES (%s, %s, %s, %s, %s, 'Abierto', 'Nivel 1', 'Agente IA')",
            (ticket_id, usuario_id, descripcion, categoria, prioridad),
        )
        conn.commit()
    finally:
        conn.close()
    _log(usuario_id, ticket_id, "Crear ticket", "crear_ticket()", "Exitoso")
    return {"ticket_id": ticket_id, "estado": "Abierto", "mensaje": f"Ticket {ticket_id} creado correctamente."}


def consultar_ticket(ticket_id: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {"error": f"No se encontró el ticket {ticket_id}."}
    return {
        "ticket_id": row["ticket_id"],
        "estado": row["estado"],
        "prioridad": row["prioridad"],
        "responsable": row["responsable"],
        "fecha_creacion": str(row["fecha_creacion"]),
        "ultima_actualizacion": str(row["ultima_actualizacion"]),
    }


def actualizar_ticket(ticket_id: str, nueva_informacion: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
        row = cur.fetchone()
        if not row:
            return {"error": f"No se encontró el ticket {ticket_id}."}

        historial = (row["historial"] or "") + f"\n[ahora] {nueva_informacion}"
        cur.execute(
            "UPDATE tickets SET historial = %s, ultima_actualizacion = NOW() WHERE ticket_id = %s",
            (historial, ticket_id),
        )
        conn.commit()
        usuario_id = row["usuario_id"]
    finally:
        conn.close()
    _log(usuario_id, ticket_id, "Actualizar ticket", "actualizar_ticket()", "Exitoso")
    return {"ticket_id": ticket_id, "mensaje": "Ticket actualizado correctamente."}


def escalar_ticket(ticket_id: str, motivo: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))
        row = cur.fetchone()
        usuario_id = row["usuario_id"] if row else None
        if row:
            cur.execute(
                "UPDATE tickets SET estado = 'Escalado', nivel = 'Nivel 2', "
                "responsable = 'Soporte N2', ultima_actualizacion = NOW() WHERE ticket_id = %s",
                (ticket_id,),
            )
            conn.commit()
    finally:
        conn.close()
    _log(usuario_id, ticket_id, "Escalar ticket", "escalar_ticket()", "Exitoso")
    return {"ticket_id": ticket_id, "estado": "Escalado a Nivel 2", "motivo": motivo}


def _enviar_correo(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """
    Envía un correo real por SMTP usando las variables del .env.
    Devuelve True si se envió, False si no se pudo (y lo deja registrado en consola
    para que puedas depurarlo, en vez de fallar la conversación completa).
    """
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    usuario_smtp = os.getenv("SMTP_USER")
    password_smtp = os.getenv("SMTP_PASSWORD")
    remitente = os.getenv("SMTP_FROM", usuario_smtp)

    if not all([host, usuario_smtp, password_smtp]):
        print("[EMAIL] Configuración SMTP incompleta en .env; no se envió el correo.")
        return False

    msg = MIMEText(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(usuario_smtp, password_smtp)
            server.sendmail(remitente, [destinatario], msg.as_string())
        print(f"[EMAIL] Correo enviado a {destinatario}")
        return True
    except Exception as e:
        print(f"[EMAIL] Error al enviar correo: {e}")
        return False


def restablecer_credencial(usuario_id: int, correo_confirmado: str) -> dict:
    """
    Restablece la contraseña de LOGIN de la plataforma (no la de Gmail/correo real
    del usuario, esa es ajena al sistema).

    Seguridad clave: `usuario_id` viene SIEMPRE del JWT de la sesión autenticada
    (nunca del texto del chat ni de lo que decida el modelo), así que esta función
    únicamente puede modificar la cuenta de quien está logueado en ese momento.
    Es físicamente imposible que el agente resetee la contraseña de otra cuenta,
    sin importar qué escriba el usuario en el chat.

    `correo_confirmado` es el correo que el usuario escribió en el chat para
    "demostrar" su identidad. Aquí, en el backend (no el modelo), se compara
    contra el correo real guardado en la base de datos para ESE usuario_id.
    Si no coincide, se rechaza y no se cambia nada.
    """
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT email, nombre FROM usuarios WHERE usuario_id = %s", (usuario_id,))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return {"resultado": "error", "mensaje": "No se encontró la cuenta autenticada."}

    correo_real = row["email"].strip().lower()
    correo_dado = (correo_confirmado or "").strip().lower()

    if correo_dado != correo_real:
        _log(usuario_id, None, "Restablecer credencial", "restablecer_credencial()", "Rechazado")
        return {
            "resultado": "rechazado",
            "mensaje": (
                "El correo indicado no coincide con el correo registrado en esta cuenta. "
                "No se realizó ningún cambio."
            ),
        }

    # Identidad verificada -> generar clave temporal y actualizar el hash REAL en la BD
    nueva_clave_temp = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    nuevo_hash = hash_password(nueva_clave_temp)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE usuarios SET password_hash = %s WHERE usuario_id = %s",
            (nuevo_hash, usuario_id),
        )
        conn.commit()
    finally:
        conn.close()

    enviado = _enviar_correo(
        destinatario=correo_real,
        asunto="Restablecimiento de contraseña - Agente IA Soporte Nivel 1",
        cuerpo=(
            f"Hola {row['nombre']},\n\n"
            f"Tu contraseña de acceso al portal de soporte fue restablecida.\n\n"
            f"Contraseña temporal: {nueva_clave_temp}\n\n"
            f"Inicia sesión con esta clave y cámbiala de inmediato por una nueva.\n\n"
            f"Si tú no solicitaste este cambio, contacta a soporte de inmediato."
        ),
    )

    _log(
        usuario_id, None, "Restablecer credencial", "restablecer_credencial()",
        "Exitoso" if enviado else "Exitoso (correo no enviado)",
    )

    if enviado:
        return {
            "resultado": "exitoso",
            "mensaje": f"Contraseña restablecida correctamente. Se envió una contraseña temporal a {correo_real}.",
        }

    # El cambio en la BD sí ocurrió; el correo no se pudo enviar (ej. SMTP mal configurado).
    # Se devuelve la clave aquí solo como respaldo para no dejar al usuario sin acceso.
    return {
        "resultado": "exitoso_sin_correo",
        "mensaje": (
            f"La contraseña se restableció correctamente, pero no fue posible enviar el correo "
            f"(revisa la configuración SMTP del servidor). Contraseña temporal: {nueva_clave_temp}"
        ),
    }


def diagnosticar_equipo(usuario_id: int) -> dict:
    conectividad = random.choice(["Disponible", "No disponible"])
    resultado = {
        "conectividad": conectividad,
        "servicios_criticos": "Disponibles" if conectividad == "Disponible" else "No verificables",
        "uso_memoria": f"{random.randint(35, 90)}%",
        "espacio_disponible": f"{random.randint(5, 200)} GB",
        "dispositivo": "Equipo estándar (simulado)",
    }
    _log(usuario_id, None, "Diagnóstico", "diagnosticar_equipo()", "Exitoso")
    return resultado
