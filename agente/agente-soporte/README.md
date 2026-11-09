# Agente Inteligente de IA — Soporte Técnico Nivel 1

Prototipo funcional basado en el informe "Agente Inteligente de IA para
Automatización y Resolución de Incidencias de Soporte Técnico de Nivel 1".

Implementa el MVP recomendado en la sección 1.15 del informe:
**FastAPI + base de datos + interfaz web + GPT-5 mini + herramientas (tools)**.

## Qué incluye

| Archivo | Contenido |
|---|---|
| `main.py` | Servidor FastAPI: endpoint `/chat` + interfaz web |
| `agent.py` | Lógica del agente: prompt, definición de tools, bucle de function-calling con OpenAI |
| `tools.py` | Las 6 herramientas del informe, con persistencia en SQLite (`tickets.db`, se crea sola) |
| `static/index.html` | Interfaz de chat simple |
| `.env.example` | Plantilla para tu clave de OpenAI |

Herramientas implementadas: `crear_ticket`, `consultar_ticket`, `actualizar_ticket`,
`escalar_ticket`, `restablecer_credencial`, `diagnosticar_equipo`.

## 1. Instalar dependencias

```bash
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Configurar tu API key

```bash
cp .env.example .env
```

Edita `.env` y pega tu clave real de OpenAI (la que viste en tu panel de proyecto,
con prefijo `sk-...`). **Nunca subas `.env` a GitHub** — ya está en `.gitignore`.

El proyecto carga la variable automáticamente si usas `uvicorn` con `python-dotenv`,
o puedes exportarla manualmente:

```bash
export OPENAI_API_KEY="sk-tu-clave-real"      # en Windows (PowerShell): $env:OPENAI_API_KEY="sk-..."
```

## 3. Ejecutar el servidor

```bash
uvicorn main:app --reload
```

Abre `http://127.0.0.1:8000` en el navegador y conversa con el agente.

## 4. Probar el flujo completo (como en la sección 1.13 del informe)

Prueba escribiendo algo como:

> "No puedo conectarme a Internet desde mi computadora."

El agente debería: hacer una pregunta de contexto → ejecutar `diagnosticar_equipo()`
→ si no se resuelve, ejecutar `crear_ticket()` y `escalar_ticket()` → confirmarte
el número de ticket, igual que el ejemplo del informe.

## Próximos pasos sugeridos

- **Base de conocimientos (RAG):** por ahora el agente razona solo con el prompt.
  Para el paso descrito en la sección 1.4.3, se puede agregar una carpeta de
  manuales/FAQ y recuperación con embeddings antes de responder.
- **Autenticación real de usuarios:** hoy `usuario_id` es un texto libre que
  escribe el usuario; en producción debe venir de tu sistema de login (JWT,
  como propone la sección 1.15).
- **Reemplazar las herramientas simuladas** (`tools.py`) por llamadas reales a
  tu sistema de tickets / directorio de credenciales / monitoreo.
- **Persistencia de sesiones:** actualmente el historial de chat vive en memoria
  del proceso; para producción, mover a Redis o PostgreSQL.
- **Migrar SQLite → PostgreSQL** cuando pases de prototipo a producción, tal
  como indica el informe.

## Seguridad

- La API key nunca se expone al navegador: solo vive en el backend (`.env`).
- `restablecer_credencial()` exige una bandera `identidad_validada` — el
  prompt del agente está instruido para no marcarla en verdadero sin que el
  usuario confirme su identidad primero (guardrail de la sección 1.10).
- Todas las acciones quedan registradas en la tabla `auditoria` de `tickets.db`
  (sección 1.11 del informe).
