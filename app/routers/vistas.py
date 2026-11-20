"""
tres modos: consulta, nuevo, editar.
Este archivo solo arma el contexto y devuelve la plantilla; 
y las reglas de negocio irán en services/.
"""
import os
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse
import logging
from datetime import date
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.conexion import Conexion
from app.plantillas import templates
from app.repos import pedidos_repository
from app.repos.catalogos_repository import CatalogosRepository as Catalogos
from app.services.pedidos_service import PedidoService
router = APIRouter(include_in_schema=False)

logger = logging.getLogger(__name__)
IVA = 0.19  # ajustar al IVA real
CAMPOS = {"numero_pedido": "Pedido No", "proveedor": "Proveedor", "orden_compra": "Orden de Compra"}
MSG_VACIO = "No se encontró información para mostrar."


# ============================================================ utilidades
def _dia(v) -> str:
    return str(v)[:10] if v else ""


def _txt(v) -> str:
    return "" if v is None else str(v)


def _clase_estado(e) -> str:
    return "anu" if e == 9 else "rec" if e in (3, 4) else "pend"


def _tipo_pedido(tpo_prvdor) -> int:
    """Regla del FoxPro: sin dato -> 0, tpo_prvdor 4 -> Internacional (2), otro -> Nacional (1)."""
    return 0 if tpo_prvdor is None else 2 if tpo_prvdor == 4 else 1


def _catalogos() -> dict:
    """Combos que necesitan los modos nuevo y editar."""
    return {
        "proveedores": Catalogos.proveedores(),
        "niveles": Catalogos.niveles_limpieza(),
        "bodegas": Catalogos.bodegas(),
    }


def _pagina(request: Request, ctx: dict) -> HTMLResponse:
    return templates.TemplateResponse(request, "solicitud_compra.html", ctx)



# ============================================================ contexto
def _contexto(modo: str = "consulta", campo: str = "numero_pedido", valor: str = "",
              mensaje: str | None = None) -> dict:
    """Contexto vacío: todas las claves que usa la plantilla."""
    return {
        "modo": modo, "editable": modo in ("nuevo", "editar"),
        "campos": CAMPOS, "campo": campo, "valor": valor, "mensaje": mensaje,
        "cat": {}, "c": {}, "sel": {}, "lineas": [], "bars": [], "steps": [],
        "cost": 0, "total_iva": 0, "margin": 0, "contador": "",
        "nav": {"first": "#", "prev": "#", "next": "#", "last": "#", "actual": "/", "ini": True, "fin": True},
    }


def _cabecera(cab: dict) -> dict:
    return {
        "estdo": cab["estdo"], "estado": cab["estado_nombre"], "estado_clase": _clase_estado(cab["estdo"]),
        "prov": _txt(cab["idntfccion"]), "fped": _dia(cab["fcha_pddo"]), "fpac": _dia(cab["fcha_pctda"]),
        "tipo": 2 if cab["tpo_ped"] == 2 else 1, "oc": _txt(cab["orden_cmpra_int"]),
        "lote": _txt(cab["lte_int"]), "trm": cab["trm"], "bod": _txt(cab["bdga_dstno"]),
        "reg": _txt(cab["realizado"]),
        "fcha_recibido": (cab["fcha_recibido"]),
    }


def _lineas_y_resumen(filas: list[dict], sel_i: int, url_linea) -> tuple[list, list, float]:
    lineas, costo = [], 0.0
    for k, f in enumerate(filas):
        t = float(f["cntdad_pdda"] or 0) * float(f["prcio_cmpra"] or 0)
        costo += t
        lineas.append({
            "plu": f["cdgo_plu"], "nombre": _txt(f["nmbre_prdcto"]), "bod": f'{_txt(f["lclzcion"])} - {_txt(f["nombre_localizacion"])}',
            "nivel": _txt(f["tpo_lmpza"]), "qty": f["cntdad_pdda"], "precio": f["prcio_cmpra"],
            "us": f["prcio_mnda"], "t": t, "sel": k == sel_i, "url": url_linea(k),
        })
    bars = [{"plu": x["plu"], "full": x["nombre"], "corto": x["nombre"][:10],
             "pct": round(x["t"] / costo * 100) if costo else 0} for x in lineas[:8]]
    return lineas, bars, costo


def _avance(cab: dict) -> list[dict]:
    e = cab["estdo"]
    anulado, recibido = e == 9, e in (3, 4)
    pasos = [("Pedido", _dia(cab["fcha_pddo"])), ("Pactado", _dia(cab["fcha_pctda"])),
             ("Anulado" if anulado else "Recibido", "completado" if recibido else "" if anulado else "pendiente")]
    hecho = 2 if recibido else 0
    return [{"t": t, "s": s, "cls": "cancel" if anulado and n == 2 else "done" if n <= hecho else ""}
            for n, (t, s) in enumerate(pasos)]


def contexto_consulta(campo: str, valor: str, i: int | None, l: int, modo: str = "consulta") -> dict:
    """Busca, navega y carga un pedido. Sirve igual para consulta y (luego) para editar."""
    campo = campo if campo in CAMPOS else "numero_pedido"
    valor = valor.strip()

    if valor and not valor.isdigit():
        return _contexto(modo, campo, valor, "Ingresa solo números.")

    numeros = pedidos_repository.buscar_numeros(**({campo: int(valor)} if valor else {}))
    if not numeros:
        return _contexto(modo, campo, valor, MSG_VACIO)

    idx = i if i is not None else (0 if valor else len(numeros) - 1)
    idx = max(0, min(len(numeros) - 1, idx))
    datos = pedidos_repository.cargar_pedido(numeros[idx])
    if datos is None:
        return _contexto(modo, campo, valor, MSG_VACIO)

    cab, filas = datos["cabecera"], datos["lineas"]

    def url(**kw) -> str:
        return "/?" + urlencode({"campo": campo, "valor": valor, **kw})

    sel_i = max(0, min(len(filas) - 1, l)) if filas else 0
    lineas, bars, costo = _lineas_y_resumen(filas, sel_i, lambda k: url(i=idx, l=k))

    ctx = _contexto(modo, campo, str(cab["nmro_pddo"]) if campo == "numero_pedido" else valor)
    ctx.update({
        "c": _cabecera(cab), "sel": lineas[sel_i] if lineas else {},
        "lineas": lineas, "bars": bars, "steps": _avance(cab),
        "cost": costo, "total_iva": costo * (1 + IVA),
        "contador": f"{idx + 1} de {len(numeros)}",
        "nav": {"first": url(i=0), "prev": url(i=idx - 1), "next": url(i=idx + 1),
                "last": url(i=len(numeros) - 1), "actual": url(i=idx),
                "ini": idx == 0, "fin": idx == len(numeros) - 1},
    })
    ctx["cat"] = _catalogos()
    return ctx


def contexto_nuevo(request: Request) -> dict:
    """Pantalla en blanco lista para ingresar: combos cargados y valores por defecto."""
    hoy = Conexion.fecha_servidor().date().isoformat()   # fecha del servidor SQL
    usuario = os.getenv("APP_USUARIO", "SIN-LOGIN")       # temporal, hasta definir el login
    terminal = request.client.host if request.client else ""
    ctx = _contexto("nuevo")
    ctx.update({
        "cat": _catalogos(),
        "c": {"estado": "NUEVO", "estado_clase": "nuevo", "fped": hoy, "fpac": hoy, "tipo": 1,
              "oc": "", "lote": "", "trm": 0, "reg": f"{usuario} - {terminal}"},
    })
    return ctx


# ============================================================ rutas
# /pedidos/nuevo va ANTES de cualquier /pedidos/{n}, para que "nuevo" no se tome como número.
@router.get("/nuevo", response_class=HTMLResponse)
def pagina_nuevo(request: Request):
    return _pagina(request, contexto_nuevo(request))

def _a_float(valor: str) -> float:
    valor = (valor or "").strip().replace(",", ".")
    return float(valor) if valor else 0.0


def _nuevo_con_error(request: Request, mensaje: str, codigo: int, ingresado: dict) -> HTMLResponse:
    """Vuelve a mostrar la pantalla 'nuevo' con el mensaje y lo que el usuario ya había escrito."""
    ctx = contexto_nuevo(request)
    ctx["mensaje"] = mensaje
    ctx["c"].update({
        "fped": ingresado["fecha_pedido"],
        "fpac": ingresado["fecha_pactada"],
        "lote": ingresado["lote"],
        "bod": ingresado["bodega"],
        "internacional": ingresado["tipo_pedido"] == "internacional",
    })
    ctx["sel"] = {"plu": ingresado["codigo_plu"], "nivel": ingresado["nivel"]}
    return templates.TemplateResponse(
        request, "solicitud_compra.html", ctx, status_code=codigo
    )


@router.post("/nuevo", response_class=HTMLResponse)
def guardar_nuevo(
    request: Request,
    proveedor: int = Form(...),
    fecha_pedido: date = Form(...),
    fecha_pactada: date = Form(...),
    tipo_pedido: str = Form("nacional"),
    lote: str = Form(""),
    trm: str = Form(""),
    bodega: str = Form(...),
    codigo_plu: int = Form(...),
    nivel: int = Form(...),
    cant: str = Form(...),
    precio: str = Form(...),
    precio_us: str = Form(""),
):
    ingresado = {
        "fecha_pedido": fecha_pedido.isoformat(),
        "fecha_pactada": fecha_pactada.isoformat(),
        "lote": lote, "bodega": bodega, "tipo_pedido": tipo_pedido,
        "codigo_plu": codigo_plu, "nivel": nivel,
    }

    cabecera = {
        "codigo_proveedor": proveedor,
        "fecha_pedido": fecha_pedido,
        "fecha_pactada": fecha_pactada,
        "tipo_pedido": 2 if tipo_pedido == "internacional" else 1,
        "lote_interno": lote.strip() or None,
        "trm": _a_float(trm),
        "bodega_destino": bodega,
    }  # el usuario lo completa PedidosService

    detalles = [{
        "codigo_plu": codigo_plu,
        "cantidad_pedida": _a_float(cant),
        "nivel": nivel,
        "precio": _a_float(precio),
        "precio_us": _a_float(precio_us),
    }]

    try:
        resultado = PedidoService.crear_pedido(cabecera, detalles)

    except ValueError as error:
        logger.warning("Validación al crear pedido: %s", error)
        return _nuevo_con_error(request, str(error), 400, ingresado)

    except IntegrityError:
        logger.exception("Error de integridad en SQL Server")
        return _nuevo_con_error(request, "Conflicto de datos al registrar el pedido.", 409, ingresado)

    except SQLAlchemyError:
        logger.exception("Error de SQLAlchemy al crear pedido")
        return _nuevo_con_error(request, "Error al guardar el pedido en la base de datos.", 500, ingresado)

    except Exception:
        logger.exception("Error inesperado al crear pedido")
        return _nuevo_con_error(request, "Ocurrió un error inesperado al crear el pedido.", 500, ingresado)

    # 303: el navegador pasa a GET y un refresco no reenvía el formulario
    return RedirectResponse(f"/?valor={resultado['numero_pedido']}", status_code=303)


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request, campo: str = "numero_pedido", valor: str = "",
           i: int | None = None, l: int = 0):
    return _pagina(request, contexto_consulta(campo, valor, i, l))
