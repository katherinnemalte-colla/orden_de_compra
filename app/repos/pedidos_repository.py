
from datetime import date, timedelta

from app.conexion import Conexion

ESTADOS = {2: "PENDIENTE", 4: "RECIBIDO", 9: "ANULADO"}


def _rango_dia(campo: str, nombre: str, dia: date, where: list, params: dict) -> None:
    """Filtra un día completo sin usar CAST sobre la columna (así usa el índice)."""
    where.append(f"{campo} >= :{nombre}_ini AND {campo} < :{nombre}_fin")
    params[f"{nombre}_ini"] = dia
    params[f"{nombre}_fin"] = dia + timedelta(days=1)


def buscar_numeros(
    numero_pedido: int | None = None,
    proveedor: int | None = None,
    fecha_pactada: date | None = None,
    fecha_pedido: date | None = None,
    solo_pendientes: bool = False,
    lote_int: int | None = None,
    orden_compra: int | None = None,
) -> list[int]:
    """Lista de números de pedido que cumplen los filtros (para el navegador)."""
    where = ["1=1"]
    params: dict = {}

    if numero_pedido:
        where.append("nmro_pddo = :numero_pedido")
        params["numero_pedido"] = numero_pedido
    if proveedor:
        where.append("idntfccion = :proveedor")
        params["proveedor"] = proveedor
    if fecha_pactada:
        _rango_dia("fcha_pctda", "fpac", fecha_pactada, where, params)
    if fecha_pedido:
        _rango_dia("fcha_pddo", "fped", fecha_pedido, where, params)
    if solo_pendientes:
        where.append("estdo = 2")
    if lote_int:
        where.append("lte_int = :lote_int")
        params["lote_int"] = lote_int
    if orden_compra:
        where.append("orden_cmpra_int = :orden_compra")
        params["orden_compra"] = orden_compra

    sql = (
        "SELECT nmro_pddo FROM pddos_prvdor WHERE "
        + " AND ".join(where)
        + " GROUP BY nmro_pddo ORDER BY nmro_pddo ASC"
    )
    return [f["nmro_pddo"] for f in Conexion.consultar(sql, params)]


def cargar_pedido(numero_pedido: int) -> dict | None:
    """Cabecera y líneas de un pedido. None si no existe."""
    cab = Conexion.consultar(
        """
        SELECT a.nmro_pddo, a.orden_cmpra_int, a.idntfccion, c.nmbre_prvdor,
               a.fcha_pddo, a.fcha_pctda, a.estdo, a.lte_int, a.trm, a.tpo_ped,
               a.bdga_dstno, a.realizado, a.recibido, a.fcha_recibido
        FROM pddos_prvdor a
        LEFT JOIN prvdres c ON c.idntfccion = a.idntfccion
        WHERE a.nmro_pddo = :n
        """,
        {"n": numero_pedido},
    )
    if not cab:
        return None

    lineas = Conexion.consultar(
        """
        SELECT b.cdgo_plu, d.nmbre_prdcto, b.tpo_lmpza, b.lclzcion, l.nmbre AS nombre_localizacion,
               b.cntdad_pdda, b.cntdad_rcbda, b.pso_rcbdo,
               b.prcio_cmpra, b.prcio_mnda, b.nmro_lte, b.lte_prvdor,
               CASE WHEN d.envse = 'GRN' THEN d.undad ELSE d.envse END AS unidad
        FROM pddo_prdcto b
        INNER JOIN prdctos d ON d.cdgo_plu = b.cdgo_plu
        LEFT JOIN lclzcnes l
        ON l.lclzcion = b.lclzcion
        WHERE b.nmro_pddo = :n
        ORDER BY d.nmbre_prdcto
        """,
        {"n": numero_pedido},
    )

    cabecera = cab[0]
    cabecera["estado_nombre"] = ESTADOS.get(cabecera["estdo"], f"ESTADO {cabecera['estdo']}")
    return {"cabecera": cabecera, "lineas": lineas}