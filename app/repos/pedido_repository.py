
from sqlalchemy import text
from sqlalchemy.engine import Connection


class PedidoRepository:
    """
    Repositorio encargado de las operaciones de la cabecera
    de los pedidos de proveedor.

    Recibe una conexión SQLAlchemy activa.
    No administra transacciones ni realiza commit/rollback.
    """

    def __init__(self, connection: Connection):
        self.connection = connection

    def insertar_pedido(self, datos_pedido: dict) -> int:
        """
        Inserta la cabecera de un pedido en pddos_prvdor.

        Retorna la cantidad de filas afectadas.
        """

        sql = text("""
            INSERT INTO pddos_prvdor (
                nmro_pddo,
                idntfccion,
                fcha_pddo,
                fcha_pctda,
                nmro_rcbo,
                estdo,
                realizado,
                actlzcion,
                lte_int,
                trm,
                tpo_ped,
                bdga_dstno,
                fcha_realizado
            )
            VALUES (
                :numero_pedido,
                :codigo_proveedor,
                :fecha_pedido,
                :fecha_pactada,
                :numero_recibo,
                :estado,
                :usuario,
                :fecha_servidor,
                :lote_interno,
                :trm,
                :tipo_pedido,
                :bodega_destino,
                :fecha_servidor
            )
        """)

        parametros = {
            "numero_pedido": datos_pedido["numero_pedido"],
            "codigo_proveedor": datos_pedido["codigo_proveedor"],
            "fecha_pedido": datos_pedido["fecha_pedido"],
            "fecha_pactada": datos_pedido["fecha_pactada"],
            "numero_recibo": datos_pedido["numero_pedido"],
            "estado": 2,
            "usuario": datos_pedido["usuario"],
            "fecha_servidor": datos_pedido["fecha_servidor"],
            "lote_interno": datos_pedido["lote_interno"],
            "trm": datos_pedido["trm"],
            "tipo_pedido": datos_pedido["tipo_pedido"],
            "bodega_destino": datos_pedido["bodega_destino"],
        }

        resultado = self.connection.execute(sql, parametros)

        return resultado.rowcount
