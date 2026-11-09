"""
auth.py
Registro, login, hashing de contraseñas (bcrypt) y emisión/verificación
de tokens JWT para proteger los endpoints del agente.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException
from passlib.hash import bcrypt

from db import get_conn

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "Falta JWT_SECRET en tu archivo .env. Genera una clave larga y aleatoria "
        "(ej: python -c \"import secrets; print(secrets.token_hex(32))\")."
    )
ALGORITHM = "HS256"
EXPIRA_MINUTOS = 60 * 24 * 7  # el token dura 7 días


# ---------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hash(password)


def verificar_password(password: str, password_hash: str) -> bool:
    return bcrypt.verify(password, password_hash)


# ---------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------
def crear_token(usuario_id: int, email: str) -> str:
    payload = {
        "sub": str(usuario_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRA_MINUTOS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="La sesión expiró, inicia sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")


def usuario_actual(authorization: str = Header(None)) -> dict:
    """
    Dependency de FastAPI: exige un header 'Authorization: Bearer <token>'
    y devuelve {"usuario_id": int, "email": str}.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autenticado.")
    token = authorization.removeprefix("Bearer ").strip()
    payload = _decodificar_token(token)
    return {"usuario_id": int(payload["sub"]), "email": payload["email"]}


# ---------------------------------------------------------------------
# Registro / login contra la tabla `usuarios`
# ---------------------------------------------------------------------
def registrar_usuario(nombre: str, email: str, password: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT usuario_id FROM usuarios WHERE email = %s", (email,))
        if cur.fetchone():
            raise ValueError("Ya existe una cuenta registrada con ese correo.")

        password_hash = hash_password(password)
        cur.execute(
            "INSERT INTO usuarios (nombre, email, password_hash) VALUES (%s, %s, %s)",
            (nombre, email, password_hash),
        )
        conn.commit()
        usuario_id = cur.lastrowid
        return {"usuario_id": usuario_id, "nombre": nombre, "email": email}
    finally:
        conn.close()


def autenticar_usuario(email: str, password: str) -> dict:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM usuarios WHERE email = %s AND activo = TRUE", (email,))
        row = cur.fetchone()
        if not row or not verificar_password(password, row["password_hash"]):
            raise ValueError("Correo o contraseña incorrectos.")

        cur.execute(
            "UPDATE usuarios SET ultimo_login = NOW() WHERE usuario_id = %s",
            (row["usuario_id"],),
        )
        conn.commit()
        return row
    finally:
        conn.close()
