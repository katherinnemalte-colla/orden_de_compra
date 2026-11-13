from decimal import Decimal
from typing import Any

from app.conexion import Conexion


def _entero(v: Any) -> Any:
    """decimal(16,0) llega como Decimal; lo pasamos a int para no mostrar '12.0'."""
    return int(v) if isinstance(v, Decimal) and v == v.to_integral_value() else v


class CatalogosRepository:

    @classmethod
    def _combo(cls, sql: str, params: dict | None = None) -> list[dict]:
        """Ejecuta un SELECT de dos columnas (código, nombre) y concatena ambas."""
        combo = []
        for fila in Conexion.consultar(sql, params):
            codigo, nombre = list(fila.values())[:2]
            codigo = _entero(codigo)
            combo.append({"valor": codigo, "texto": f"{codigo} - {str(nombre or '').strip()}"})
        return combo

    # ---------- combos ----------
    @classmethod
    def proveedores(cls) -> list[dict]:
        return cls._combo("SELECT idntfccion, nmbre_prvdor FROM prvdres ORDER BY nmbre_prvdor")

    @classmethod
    def niveles_limpieza(cls) -> list[dict]:
        return cls._combo("SELECT tpo_lmpza, nmbre FROM tpo_lmpza ORDER BY tpo_lmpza")

    @classmethod
    def bodegas(cls) -> list[dict]:
        return cls._combo("SELECT lclzcion, nmbre FROM lclzcnes ORDER BY lclzcion")

    # ---------- consultas por código (validan que existan) ----------
    @classmethod
    def tipo_proveedor(cls, idntfccion: int) -> int | None:
        filas = Conexion.consultar(
            "SELECT tpo_prvdor FROM prvdres WHERE idntfccion = :id", {"id": idntfccion}
        )
        return filas[0]["tpo_prvdor"] if filas else None

    @classmethod
    def producto(cls, cdgo_plu: int) -> dict | None:
        filas = Conexion.consultar(
            "SELECT cdgo_plu, nmbre_prdcto FROM prdctos WHERE cdgo_plu = :plu", {"plu": cdgo_plu}
        )
        if not filas:
            return None
        return {"plu": filas[0]["cdgo_plu"], "nombre": str(filas[0]["nmbre_prdcto"] or "").strip()}