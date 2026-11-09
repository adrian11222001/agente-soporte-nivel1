"""
db.py
Conexión a MySQL mediante un connection pool.
Requiere las variables de entorno definidas en .env (ver .env.example).
"""

import os
from dotenv import load_dotenv
from mysql.connector import pooling

load_dotenv()

_dbconfig = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "soporte_ia"),
}

_pool = pooling.MySQLConnectionPool(
    pool_name="soporte_pool",
    pool_size=5,
    **_dbconfig,
)


def get_conn():
    """Devuelve una conexión del pool. Recuerda cerrarla (conn.close()) al terminar."""
    return _pool.get_connection()
