from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.plantillas import templates
from app.repos import pedidos_repository
from app.services import pedidos_service

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
    numeros = pedidos_repository.buscar_numeros(
        numero_pedido, proveedor, fecha_pactada, fecha_pedido,
        solo_pendientes, lote_int, orden_compra,
    )
    return {"total": len(numeros), "pedidos": numeros}

# ---------- NUEVO PEDIDO ----------
@router.get("/nuevo", response_class=HTMLResponse)
def nuevo(request: Request):

    ctx = {
        "campos": {
            "numero_pedido": "Pedido No",
            "proveedor": "Proveedor",
            "orden_compra": "Orden de Compra",
        },
        "campo": "numero_pedido",
        "valor": "",
        "mensaje": None,
        "c": {},
        "sel": {},
        "lineas": [],
        "bars": [],
        "steps": [],
        "cost": 0,
        "total_iva": 0,
        "margin": 0,
        "contador": "",
        "nav": {
            "first": "#",
            "prev": "#",
            "next": "#",
            "last": "#",
            "actual": "/",
            "ini": True,
            "fin": True,
        },
    }

    datos = pedidos_service.PedidosService.preparar_nuevo()
    ctx.update(datos)

    return templates.TemplateResponse(
        request,
        "solicitud_compra.html",
        ctx
    )

@router.get("/{numero_pedido}")
def obtener(numero_pedido: int):
    datos = pedidos_repository.cargar_pedido(numero_pedido)
    if datos is None:
        raise HTTPException(status_code=404, detail="No se encontró información para mostrar.")
    return datos