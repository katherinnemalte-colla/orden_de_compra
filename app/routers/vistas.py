"""
tres modos: consulta, nuevo, editar.
Este archivo solo arma el contexto y devuelve la plantilla; 
y las reglas de negocio irán en services/.
"""
import os
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.conexion import Conexion
from app.plantillas import templates
from app.repos import pedidos_repository
from app.repos.catalogos_repository import CatalogosRepository as Catalogos

router = APIRouter(include_in_schema=False)

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


def _parcial(macro: str, **kw) -> HTMLResponse:
    """Renderiza una macro de parciales.html (respuesta para HTMX)."""
    modulo = templates.env.get_template("parciales.html").module
    return HTMLResponse(str(getattr(modulo, macro)(**kw)))


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


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request, campo: str = "numero_pedido", valor: str = "",
           i: int | None = None, l: int = 0):
    return _pagina(request, contexto_consulta(campo, valor, i, l))



# ------------------------------------------- fragmentos HTMX (nuevo y editar)
@router.get("/parciales/producto", response_class=HTMLResponse)
def parcial_producto(plu: str = ""):
    """Cod. Plu -> valida que exista y autollena el nombre del producto."""
    plu = plu.strip()
    if not plu:
        return _parcial("nombre_producto")
    if not plu.isdigit():
        return _parcial("nombre_producto", error="El código debe ser numérico.")
    prod = Catalogos.producto(int(plu))
    if prod is None:
        return _parcial("nombre_producto", error="El producto no existe.")
    return _parcial("nombre_producto", nombre=prod["nombre"])


@router.get("/parciales/tipo", response_class=HTMLResponse)
def parcial_tipo(proveedor: str = ""):
    """Proveedor -> define Tipo Pedido."""
    tipo = 0
    if proveedor.strip().isdigit():
        tipo = _tipo_pedido(Catalogos.tipo_proveedor(int(proveedor)))
    return _parcial("tipo_pedido", tipo=tipo)