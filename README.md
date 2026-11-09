# Agente Inteligente de IA para Soporte Técnico de Nivel 1

Prototipo de un agente de IA que automatiza la atención de incidencias de soporte técnico de Nivel 1. A diferencia de un chatbot de preguntas frecuentes, el agente **ejecuta acciones reales** mediante herramientas (function calling): crea y consulta tickets, los escala a Nivel 2, restablece credenciales y realiza diagnósticos básicos, dejando registro de cada acción.

Proyecto desarrollado para el curso de **Tecnología Emergente** (Escuela Profesional de Ingeniería de Sistemas, Universidad Nacional Federico Villarreal).

## Características

- Chat web con inicio de sesión y varias conversaciones por usuario, guardadas en MySQL.
- Agente basado en **GPT-5 mini** (Responses API de OpenAI) con un ciclo de herramientas de hasta 8 iteraciones.
- Seis herramientas: crear, consultar, actualizar y escalar tickets; restablecer credencial; diagnosticar equipo.
- Autenticación con **JWT** y contraseñas con **bcrypt**.
- Identidad del usuario tomada del token (el modelo no puede suplantar a otra cuenta).
- Validación de identidad en el servidor para restablecer credenciales (envío de clave temporal por correo SMTP).
- Auditoría de todas las acciones del agente.
- Despliegue con **Docker Compose** (aplicación + base de datos).

## Arquitectura

```
Usuario ─► Interfaz web ─► FastAPI ─► Agente (GPT-5 mini)
                                         │
                                         ├─► Herramientas (tools.py)
                                         │      ├─ Tickets
                                         │      ├─ Credenciales (SMTP)
                                         │      └─ Diagnóstico
                                         │
                                         └─► MySQL (usuarios, conversaciones,
                                                    mensajes, tickets, auditoría)
```

## Tecnologías

| Componente | Tecnología |
|---|---|
| Modelo de lenguaje | GPT-5 mini (OpenAI) |
| Backend | Python 3.12 + FastAPI |
| Base de datos | MySQL 8 |
| Autenticación | JWT (PyJWT) + bcrypt (passlib) |
| Frontend | HTML, CSS y JavaScript |
| Contenedores | Docker y Docker Compose |

## Estructura del proyecto

```
agente-soporte/
├── main.py              # API FastAPI: login, conversaciones y /chat
├── agent.py             # Prompt, definición de herramientas y ciclo del agente
├── tools.py             # Implementación de las 6 herramientas
├── auth.py              # Registro, login, bcrypt y JWT
├── conversaciones.py    # Persistencia de conversaciones y mensajes
├── db.py                # Pool de conexiones a MySQL
├── schema.sql           # Esquema de la base de datos
├── static/              # Interfaz web (index.html, app.js, style.css)
├── requirements.txt
├── .env.example         # Plantilla de variables de entorno
├── Dockerfile
└── docker-compose.yml
```

## Requisitos

- Docker y Docker Compose (recomendado), **o** Python 3.12 y MySQL 8.
- Una API key de OpenAI.
- Opcional: una cuenta de correo con SMTP para enviar contraseñas temporales (en Gmail, usa una *contraseña de aplicación*).

## Instalación y ejecución

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/agente-soporte-nivel1.git
cd agente-soporte-nivel1
```

### 2. Configurar las variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus valores:

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI |
| `OPENAI_MODEL` | Modelo a usar (por defecto `gpt-5-mini`) |
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` | Conexión a MySQL |
| `JWT_SECRET` | Clave larga y aleatoria para firmar los tokens |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Envío de correos |

Para generar `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Importante:** nunca subas el archivo `.env` al repositorio. Ya está incluido en `.gitignore`.

### 3. Levantar con Docker

```bash
docker compose up --build
```

Cuando veas `Application startup complete`, abre <http://localhost:8000>.

> Con Docker, `MYSQL_HOST` debe coincidir con el nombre del servicio de la base de datos definido en `docker-compose.yml`.

### Alternativa: ejecución local sin Docker

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
mysql -u root -p < schema.sql     # crea la base de datos y las tablas
uvicorn main:app --reload
```

> Se requiere `openai>=1.66.0`, porque el agente usa la Responses API.

## Uso

1. Regístrate e inicia sesión en la interfaz web.
2. Escribe una incidencia, por ejemplo:
   - *"No puedo conectarme a Internet desde mi computadora."*
   - *"¿Cuál es el estado de mi ticket INC-000125?"*
   - *"Olvidé mi contraseña."* (el agente te pedirá confirmar tu correo registrado)
3. Observa en la consola del servidor las acciones ejecutadas (`[ACCIÓN EJECUTADA]`).

La documentación interactiva de la API está disponible en <http://localhost:8000/docs>.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/registro` | Crea una cuenta |
| POST | `/api/login` | Inicia sesión y devuelve un token JWT |
| GET / POST | `/api/conversaciones` | Lista o crea conversaciones |
| GET | `/api/conversaciones/{id}/mensajes` | Mensajes de una conversación |
| DELETE | `/api/conversaciones/{id}` | Elimina una conversación |
| POST | `/chat` | Envía un mensaje al agente |

Todas las rutas, salvo registro y login, requieren la cabecera `Authorization: Bearer <token>`.

## Herramientas del agente

| Herramienta | Función |
|---|---|
| `crear_ticket()` | Crea una nueva incidencia |
| `consultar_ticket()` | Consulta el estado de un ticket |
| `actualizar_ticket()` | Agrega información a un ticket |
| `escalar_ticket()` | Deriva el ticket a Nivel 2 |
| `restablecer_credencial()` | Restablece la contraseña tras validar el correo registrado |
| `diagnosticar_equipo()` | Comprobaciones técnicas básicas |

El agente **no puede** ejecutar comandos arbitrarios, eliminar usuarios o datos, ni modificar configuraciones críticas.

## Seguridad

- Contraseñas almacenadas solo como hash bcrypt.
- Tokens JWT con expiración (7 días).
- El `usuario_id` se obtiene del token y se inyecta en las herramientas; el modelo no lo controla.
- La validación del correo para restablecer credenciales se hace en el servidor, no en el modelo.
- Cada conversación solo es accesible por su propietario.
- Auditoría de las acciones en la tabla `auditoria`.
- La API key de OpenAI vive solo en el servidor.

## Estado del prototipo y limitaciones

| Componente | Estado |
|---|---|
| Chat, login, conversaciones y tickets | Implementado |
| Restablecimiento de credenciales por correo | Implementado |
| `diagnosticar_equipo()` | Simulado (valores aleatorios) |
| Base de conocimientos (RAG) | Pendiente |
| Roles (`usuario`, `agente_n2`, `admin`) | Almacenados, aún sin efecto en los accesos |
| Panel para Nivel 2 | Pendiente |

Limitaciones conocidas:

- `consultar_ticket`, `actualizar_ticket` y `escalar_ticket` aún no verifican que el ticket pertenezca al usuario autenticado.
- Si falla el envío del correo, la clave temporal se muestra en el chat (útil para demostraciones; debe eliminarse en producción).
- No hay límite de intentos de inicio de sesión ni revocación de tokens.

## Trabajo futuro

- Base de conocimientos con recuperación de documentos (RAG).
- Integración con sistemas reales de mesa de ayuda, inventario y monitoreo.
- Panel para Nivel 2 y tablero de métricas.
- Verificación de identidad con enlace o código de un solo uso.
- Pruebas automatizadas.

## Autores

- Briceño Valderrama, Adrian Marx
- Vivas Ccarapa, Kevin Walter

Profesor del curso: Jorge Lira Camargo.

## Licencia

Indica aquí la licencia elegida (por ejemplo, MIT) o elimina esta sección.
