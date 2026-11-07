from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.plantillas import templates
from app.repos import pedidos

router = APIRouter(include_in_schema=False)

IVA = 0.19  # ajustar al IVA real
CAMPOS = {"numero_pedido": "Pedido No", "proveedor": "Proveedor", "orden_compra": "Orden de Compra"}


def _dia(v) -> str:
    return str(v)[:10] if v else ""


def _txt(v) -> str:
    return "" if v is None else str(v)


def _base(campo: str, valor: str, mensaje: str | None = None) -> dict:
    return {
        "campos": CAMPOS, "campo": campo, "valor": valor, "mensaje": mensaje,
        "c": {}, "sel": {}, "lineas": [], "bars": [], "steps": [],
        "cost": 0, "total_iva": 0, "margin": 0, "contador": "",
        "nav": {"first": "#", "prev": "#", "next": "#", "last": "#", "actual": "/", "ini": True, "fin": True},
    }


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request, campo: str = "numero_pedido", valor: str = "", i: int | None = None, l: int = 0):
    campo = campo if campo in CAMPOS else "numero_pedido"
    valor = valor.strip()

    def responder(ctx):
        return templates.TemplateResponse(request, "solicitud_compra.html", ctx)

    if valor and not valor.isdigit():
        return responder(_base(campo, valor, "Ingresa solo números."))

    numeros = pedidos.buscar_numeros(**({campo: int(valor)} if valor else {}))
    if not numeros:
        return responder(_base(campo, valor, "No se encontró información para mostrar."))

    idx = i if i is not None else (0 if valor else len(numeros) - 1)
    idx = max(0, min(len(numeros) - 1, idx))
    datos = pedidos.cargar_pedido(numeros[idx])
    if datos is None:
        return responder(_base(campo, valor, "No se encontró información para mostrar."))

    cab, filas = datos["cabecera"], datos["lineas"]

    def url(**kw) -> str:
        return "/?" + urlencode({"campo": campo, "valor": valor, **kw})

    sel_i = max(0, min(len(filas) - 1, l)) if filas else 0
    lineas, costo = [], 0.0
    for k, f in enumerate(filas):
        t = float(f["cntdad_pdda"] or 0) * float(f["prcio_cmpra"] or 0)
        costo += t
        lineas.append({
            "plu": f["cdgo_plu"], "nombre": _txt(f["nmbre_prdcto"]), "bod": _txt(f["lclzcion"]),
            "nivel": _txt(f["tpo_lmpza"]), "qty": f["cntdad_pdda"], "precio": f["prcio_cmpra"],
            "us": f["prcio_mnda"], "t": t, "sel": k == sel_i, "url": url(i=idx, l=k),
        })

    bars = [{"plu": x["plu"], "full": x["nombre"], "corto": x["nombre"][:10],
             "pct": round(x["t"] / costo * 100) if costo else 0} for x in lineas[:8]]

    e = cab["estdo"]
    anulado = e == 9
    hecho = 2 if e == 4 else 0
    pasos = [("Pedido", _dia(cab["fcha_pddo"])), ("Pactado", _dia(cab["fcha_pctda"])),
             ("Anulado" if anulado else "Recibido", "completado" if e == 4 else "" if anulado else "pendiente")]
    steps = [{"t": t, "s": s, "cls": "cancel" if anulado and n == 2 else "done" if n <= hecho else ""}
             for n, (t, s) in enumerate(pasos)]

    ctx = _base(campo, str(cab["nmro_pddo"]) if campo == "numero_pedido" else valor)
    ctx.update({
        "c": {
            "estdo": e, "estado": cab["estado_nombre"], "prov": _txt(cab["nmbre_prvdor"]),
            "fped": _dia(cab["fcha_pddo"]), "fpac": _dia(cab["fcha_pctda"]),
            "internacional": cab["tpo_ped"] == 2, "oc": _txt(cab["orden_cmpra_int"]),
            "lote": _txt(cab["lte_int"]), "trm": cab["trm"], "bod": _txt(cab["bdga_dstno"]),
            "reg": _txt(cab["realizado"]),
        },
        "sel": lineas[sel_i] if lineas else {},
        "lineas": lineas, "bars": bars, "steps": steps,
        "cost": costo, "total_iva": costo * (1 + IVA), "margin": 0,
        "contador": f"{idx + 1} de {len(numeros)}",
        "nav": {"first": url(i=0), "prev": url(i=idx - 1), "next": url(i=idx + 1),
                "last": url(i=len(numeros) - 1), "actual": url(i=idx),
                "ini": idx == 0, "fin": idx == len(numeros) - 1},
    })
    return responder(ctx)