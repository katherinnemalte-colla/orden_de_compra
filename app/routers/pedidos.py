from datetime import date

from fastapi import APIRouter, HTTPException

from app.repos import pedidos

router = APIRouter(prefix="/api/pedidos", tags=["pedidos"])


@router.get("")
def buscar(
    numero_pedido: int | None = None,
    proveedor: int | None = None,
    fecha_pactada: date | None = None,
    fecha_pedido: date | None = None,
    solo_pendientes: bool = False,
    lote_int: int | None = None,
    orden_compra: int | None = None,
):
    numeros = pedidos.buscar_numeros(
        numero_pedido, proveedor, fecha_pactada, fecha_pedido,
        solo_pendientes, lote_int, orden_compra,
    )
    return {"total": len(numeros), "pedidos": numeros}


@router.get("/{numero_pedido}")
def obtener(numero_pedido: int):
    datos = pedidos.cargar_pedido(numero_pedido)
    if datos is None:
        raise HTTPException(status_code=404, detail="No se encontró información para mostrar.")
    return datos