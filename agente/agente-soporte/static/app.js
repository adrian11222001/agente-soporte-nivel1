// ---------------------------------------------------------------
// Estado
// ---------------------------------------------------------------
let token = localStorage.getItem("token");
let modoRegistro = false;
let conversacionActual = null;

const loginScreen = document.getElementById("login-screen");
const appDiv = document.getElementById("app");

// ---------------------------------------------------------------
// Login / Registro
// ---------------------------------------------------------------
const nombreField = document.getElementById("nombre-field");
const emailField = document.getElementById("email-field");
const passwordField = document.getElementById("password-field");
const loginError = document.getElementById("login-error");
const loginTitulo = document.getElementById("login-titulo");
const loginToggle = document.getElementById("login-toggle");

loginToggle.addEventListener("click", () => {
  modoRegistro = !modoRegistro;
  loginTitulo.textContent = modoRegistro ? "Crear cuenta" : "Iniciar sesión";
  nombreField.style.display = modoRegistro ? "block" : "none";
  loginToggle.textContent = modoRegistro ? "¿Ya tienes cuenta? Inicia sesión" : "¿No tienes cuenta? Regístrate";
  loginError.textContent = "";
});

document.getElementById("login-submit").addEventListener("click", async () => {
  loginError.textContent = "";
  const email = emailField.value.trim();
  const password = passwordField.value;
  if (!email || !password) {
    loginError.textContent = "Completa correo y contraseña.";
    return;
  }
  const endpoint = modoRegistro ? "/api/registro" : "/api/login";
  const body = modoRegistro
    ? { nombre: nombreField.value.trim() || "Usuario", email, password }
    : { email, password };

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      loginError.textContent = data.detail || "Ocurrió un error.";
      return;
    }
    token = data.token;
    localStorage.setItem("token", token);
    localStorage.setItem("email", data.email);
    iniciarApp();
  } catch (err) {
    loginError.textContent = "No se pudo conectar con el servidor.";
  }
});

document.getElementById("cerrar-sesion").addEventListener("click", () => {
  localStorage.removeItem("token");
  localStorage.removeItem("email");
  token = null;
  location.reload();
});

// ---------------------------------------------------------------
// Helper para llamadas autenticadas
// ---------------------------------------------------------------
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("token");
    location.reload();
    throw new Error("No autenticado");
  }
  return res.json();
}

// ---------------------------------------------------------------
// Sidebar de conversaciones
// ---------------------------------------------------------------
const listaConv = document.getElementById("lista-conversaciones");

async function cargarConversaciones() {
  const conversaciones = await api("/api/conversaciones");
  listaConv.innerHTML = "";
  conversaciones.forEach((c) => {
    const item = document.createElement("div");
    item.className = "conv-item" + (c.conversacion_id === conversacionActual ? " activa" : "");
    item.innerHTML = `<span class="titulo">${c.titulo || "Nueva conversación"}</span><span class="borrar">✕</span>`;
    item.querySelector(".titulo").addEventListener("click", () => abrirConversacion(c.conversacion_id));
    item.querySelector(".borrar").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm("¿Eliminar esta conversación?")) return;
      await api(`/api/conversaciones/${c.conversacion_id}`, { method: "DELETE" });
      if (conversacionActual === c.conversacion_id) {
        conversacionActual = null;
        chat.innerHTML = "";
        saludoInicial();
      }
      cargarConversaciones();
    });
    listaConv.appendChild(item);
  });
}

async function abrirConversacion(conversacion_id) {
  conversacionActual = conversacion_id;
  chat.innerHTML = "";
  const mensajes = await api(`/api/conversaciones/${conversacion_id}/mensajes`);
  if (mensajes.length === 0) {
    saludoInicial();
  } else {
    mensajes.forEach((m) => addMsg(m.contenido, m.rol === "user" ? "user" : "bot"));
  }
  cargarConversaciones();
}

document.getElementById("nueva-conv").addEventListener("click", async () => {
  conversacionActual = null;
  chat.innerHTML = "";
  saludoInicial();
  cargarConversaciones();
});

// ---------------------------------------------------------------
// Chat
// ---------------------------------------------------------------
const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");

function addMsg(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function saludoInicial() {
  addMsg("Hola, soy el agente de soporte de Nivel 1. Cuéntame qué problema tienes.", "bot");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const mensaje = input.value.trim();
  if (!mensaje) return;
  addMsg(mensaje, "user");
  input.value = "";

  const thinking = addMsg("Analizando la solicitud...", "bot thinking");

  try {
    const data = await api("/chat", {
      method: "POST",
      body: JSON.stringify({ mensaje, conversacion_id: conversacionActual }),
    });
    const esNueva = conversacionActual === null;
    conversacionActual = data.conversacion_id;
    thinking.remove();
    addMsg(data.respuesta, "bot");
    if (esNueva) cargarConversaciones();
  } catch (err) {
    thinking.textContent = "Ocurrió un error al conectar con el agente.";
  }
});

// ---------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------
function iniciarApp() {
  loginScreen.style.display = "none";
  appDiv.classList.add("activo");
  document.getElementById("usuario-email").textContent = localStorage.getItem("email") || "";
  saludoInicial();
  cargarConversaciones();
}

if (token) {
  iniciarApp();
}
