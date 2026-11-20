"""

Lee la configuración del archivo .env:

Si DB_USER y DB_PASSWORD no están definidos, usa autenticación de Windows
(Trusted_Connection). Si están definidos, usa autenticación de SQL Server.

Dependencias:  pip install sqlalchemy pyodbc python-dotenv
"""
import os
from contextlib import contextmanager
from typing import Any, Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Connection, Engine

load_dotenv()


class Conexion:
    """Un único Engine (con pool) para toda la aplicación."""

    _engine: Engine | None = None

    # ---------- configuración ----------
    @classmethod
    def _url(cls) -> URL:
        servidor = os.getenv("DB_SERVER")
        base = os.getenv("DB_DATABASE")
        if not servidor or not base:
            raise RuntimeError("Faltan DB_SERVER o DB_DATABASE en el archivo .env")

        usuario = os.getenv("DB_USER")
        clave = os.getenv("DB_PASSWORD")

        query = {
            "driver": os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
            "TrustServerCertificate": "yes",  # red interna, certificado propio
        }
        if usuario and clave:
            return URL.create(
                "mssql+pyodbc",
                username=usuario,
                password=clave,
                host=servidor,
                database=base,
                query=query,
            )
        # Sin usuario/clave: autenticación de Windows
        query["Trusted_Connection"] = "yes"
        return URL.create("mssql+pyodbc", host=servidor, database=base, query=query)

    @classmethod
    def engine(cls) -> Engine:
        if cls._engine is None:
            cls._engine = create_engine(
                cls._url(),
                pool_pre_ping=True,   # descarta conexiones caídas
                pool_size=5,
                max_overflow=5,
                pool_recycle=1800,
            )
        return cls._engine

    # ---------- uso ----------
    @classmethod
    @contextmanager
    def transaccion(cls) -> Iterator[Connection]:
        """BEGIN ... COMMIT automático; ROLLBACK si ocurre un error.

        Equivale al BEGIN/COMMIT TRANSACTION.
        """
        with cls.engine().begin() as conn:
            yield conn

    @classmethod
    def consultar(cls, sql: str, params: dict[str, Any] | None = None) -> list[dict]:
        """SELECT -> lista de diccionarios. Parámetros con :nombre (no ?nombre)."""
        with cls.engine().connect() as conn:
            filas = conn.execute(text(sql), params or {})
            return [dict(f._mapping) for f in filas]

    @classmethod
    def ejecutar(cls, sql: str, params: dict[str, Any] | None = None) -> int:
        """INSERT/UPDATE/DELETE en su propia transacción. Devuelve filas afectadas."""
        with cls.transaccion() as conn:
            return conn.execute(text(sql), params or {}).rowcount

    @classmethod
    def fecha_servidor(cls):
        """Equivale a datetimesql(nCon): fecha y hora del servidor SQL."""
        return cls.consultar("SELECT GETDATE() AS ahora")[0]["ahora"]

    @classmethod
    def probar(cls) -> dict:
        return cls.consultar(
            "SELECT DB_NAME() AS base, @@SERVERNAME AS servidor, GETDATE() AS ahora"
        )[0]


if __name__ == "__main__":
    print(Conexion.probar())