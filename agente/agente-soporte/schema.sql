-- =====================================================================
-- schema.sql
-- Base de datos para "Agente IA - Soporte Técnico Nivel 1"
-- Motor: MySQL 8.x
-- =====================================================================

CREATE DATABASE IF NOT EXISTS soporte_ia
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE soporte_ia;

-- ---------------------------------------------------------------------
-- 1. USUARIOS (login)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id      INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(150)  NOT NULL,
    email           VARCHAR(150)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255)  NOT NULL,   -- guardar SIEMPRE hash (bcrypt), nunca texto plano
    rol             ENUM('usuario', 'agente_n2', 'admin') NOT NULL DEFAULT 'usuario',
    activo          BOOLEAN       NOT NULL DEFAULT TRUE,
    fecha_creacion  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultimo_login    DATETIME      NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. CONVERSACIONES (una por sesión de chat)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversaciones (
    conversacion_id VARCHAR(36)   NOT NULL PRIMARY KEY,   -- uuid, mismo que session_id
    usuario_id      INT           NOT NULL,
    titulo          VARCHAR(200)  NULL,                   -- opcional: resumen automático del tema
    fecha_creacion  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_actividad DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_conversacion_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_conversaciones_usuario ON conversaciones(usuario_id);

-- ---------------------------------------------------------------------
-- 3. MENSAJES (cada turno de una conversación)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensajes (
    mensaje_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversacion_id VARCHAR(36)   NOT NULL,
    rol             ENUM('user', 'assistant', 'function_call', 'function_call_output')
                                  NOT NULL,
    contenido       MEDIUMTEXT    NOT NULL,     -- texto del mensaje o JSON de la tool call
    herramienta     VARCHAR(100)  NULL,         -- nombre de la tool, si aplica
    fecha           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mensaje_conversacion
        FOREIGN KEY (conversacion_id) REFERENCES conversaciones(conversacion_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_mensajes_conversacion ON mensajes(conversacion_id, fecha);

-- ---------------------------------------------------------------------
-- 4. TICKETS (migrado desde tools.py / SQLite, ahora ligado a usuarios)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id             VARCHAR(20)  NOT NULL PRIMARY KEY,
    usuario_id            INT          NOT NULL,
    descripcion           TEXT         NOT NULL,
    categoria             VARCHAR(100) DEFAULT 'General',
    prioridad             ENUM('Baja','Media','Alta') DEFAULT 'Media',
    estado                VARCHAR(50)  NOT NULL DEFAULT 'Abierto',
    nivel                 VARCHAR(20)  NOT NULL DEFAULT 'Nivel 1',
    responsable           VARCHAR(100) DEFAULT 'Agente IA',
    fecha_creacion        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_actualizacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP,
    historial             TEXT         NULL,
    CONSTRAINT fk_ticket_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_tickets_usuario ON tickets(usuario_id);
CREATE INDEX idx_tickets_estado ON tickets(estado);

-- ---------------------------------------------------------------------
-- 5. AUDITORIA (migrado desde tools.py / SQLite)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auditoria (
    id_accion    VARCHAR(20)  NOT NULL PRIMARY KEY,
    usuario_id   INT          NULL,
    ticket_id    VARCHAR(20)  NULL,
    accion       VARCHAR(150) NOT NULL,
    herramienta  VARCHAR(100) NOT NULL,
    fecha        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resultado    VARCHAR(50)  NOT NULL,
    CONSTRAINT fk_auditoria_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_auditoria_ticket
        FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_auditoria_usuario ON auditoria(usuario_id);
CREATE INDEX idx_auditoria_ticket ON auditoria(ticket_id);

-- ---------------------------------------------------------------------
-- (Opcional) Usuario admin de ejemplo — cambia el hash antes de usar en real.
-- El valor de abajo es solo un placeholder, NO un hash válido.
-- Genera el hash real con bcrypt desde Python, ej:
--   from passlib.hash import bcrypt
--   bcrypt.hash("tu_password")
-- ---------------------------------------------------------------------
-- INSERT INTO usuarios (nombre, email, password_hash, rol)
-- VALUES ('Admin', 'admin@empresa.com', '<hash_bcrypt_aqui>', 'admin');
