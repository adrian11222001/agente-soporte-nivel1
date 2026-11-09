"""
main.py
Interfaz de usuario + API del agente, ahora con login y conversaciones
individuales guardadas en MySQL (una fila por conversación, como las
"pestañas" de ChatGPT/Claude).

Ejecutar:
    uvicorn main:app --reload
"""

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr

import agent
import conversaciones as conv
from auth import autenticar_usuario, crear_token, registrar_usuario, usuario_actual

app = FastAPI(title="Agente IA - Soporte Técnico Nivel 1")


# ---------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------
class RegistroRequest(BaseModel):
    nombre: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChatRequest(BaseModel):
    mensaje: str
    conversacion_id: str | None = None  # si es None, se crea una conversación nueva


class ChatResponse(BaseModel):
    respuesta: str
    conversacion_id: str


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------
@app.post("/api/registro")
def registro(req: RegistroRequest):
    try:
        usuario = registrar_usuario(req.nombre, req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = crear_token(usuario["usuario_id"], usuario["email"])
    return {"token": token, "nombre": usuario["nombre"], "email": usuario["email"]}


@app.post("/api/login")
def login(req: LoginRequest):
    try:
        usuario = autenticar_usuario(req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    token = crear_token(usuario["usuario_id"], usuario["email"])
    return {"token": token, "nombre": usuario["nombre"], "email": usuario["email"]}


# ---------------------------------------------------------------------
# Conversaciones (cada una es su propio "hilo", como una pestaña)
# ---------------------------------------------------------------------
@app.get("/api/conversaciones")
def listar(usuario: dict = Depends(usuario_actual)):
    return conv.listar_conversaciones(usuario["usuario_id"])


@app.post("/api/conversaciones")
def nueva_conversacion(usuario: dict = Depends(usuario_actual)):
    conversacion_id = conv.crear_conversacion(usuario["usuario_id"])
    return {"conversacion_id": conversacion_id}


@app.get("/api/conversaciones/{conversacion_id}/mensajes")
def mensajes(conversacion_id: str, usuario: dict = Depends(usuario_actual)):
    if not conv.es_dueno(conversacion_id, usuario["usuario_id"]):
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return conv.obtener_mensajes_para_ui(conversacion_id)


@app.delete("/api/conversaciones/{conversacion_id}")
def eliminar(conversacion_id: str, usuario: dict = Depends(usuario_actual)):
    ok = conv.eliminar_conversacion(conversacion_id, usuario["usuario_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="Conversación no encontrada.")
    return {"eliminado": True}


# ---------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, usuario: dict = Depends(usuario_actual)):
    usuario_id = usuario["usuario_id"]

    if req.conversacion_id:
        if not conv.es_dueno(req.conversacion_id, usuario_id):
            raise HTTPException(status_code=404, detail="Conversación no encontrada.")
        conversacion_id = req.conversacion_id
    else:
        conversacion_id = conv.crear_conversacion(usuario_id)

    historial = conv.obtener_historial_para_agente(conversacion_id)
    es_primer_mensaje = len(historial) == 0

    texto, nuevo_historial = agent.responder(historial, req.mensaje, usuario_id)

    # Guardamos solo los eventos nuevos que se agregaron en esta vuelta
    eventos_nuevos = nuevo_historial[len(historial):]
    for evento in eventos_nuevos:
        if evento.get("role") == "user":
            conv.guardar_mensaje(conversacion_id, "user", evento["content"])
        elif evento.get("role") == "assistant":
            conv.guardar_mensaje(conversacion_id, "assistant", evento["content"])
        elif evento.get("type") == "function_call":
            conv.guardar_mensaje(conversacion_id, "function_call", evento, herramienta=evento.get("name"))
        elif evento.get("type") == "function_call_output":
            conv.guardar_mensaje(conversacion_id, "function_call_output", evento)

    if es_primer_mensaje:
        titulo = req.mensaje.strip()[:60] or "Nueva conversación"
        conv.actualizar_titulo(conversacion_id, titulo)

    return ChatResponse(respuesta=texto, conversacion_id=conversacion_id)


# ---------------------------------------------------------------------
# Frontend estático
# ---------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
