from datetime import date
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.repos import pedidos_repository
from app.repos import catalogos_repository
router = APIRouter(prefix="/api/pedidos", tags=["pedidos"])
import os

from datetime import date
from pydantic import BaseModel
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi.responses import JSONResponse
from app.services.pedidos_service import PedidoService
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
    numeros = pedidos_repository.buscar_numeros(
        numero_pedido,
        proveedor,
        fecha_pactada,
        fecha_pedido,
        solo_pendientes,
        lote_int,
        orden_compra,
    )

    return JSONResponse(
        content={
            "total": len(numeros),
            "pedidos": numeros
        },
        status_code=200
    )

@router.get("/{numero_pedido}")
def obtener(numero_pedido: int):
    datos = pedidos_repository.cargar_pedido(numero_pedido)
    if datos is None:
        raise HTTPException(status_code=404, detail="No se encontró información para mostrar.")
    return JSONResponse(
        content=datos,
        status_code=200
        )
@router.get("/producto/{cdgo_plu}")
def obtener_producto(cdgo_plu: int):

    producto = catalogos_repository.CatalogosRepository.producto(cdgo_plu)

    if not producto:
        raise HTTPException(
            status_code=404,
            detail="No se encontró un producto con ese código PLU"
        )
    
    return producto