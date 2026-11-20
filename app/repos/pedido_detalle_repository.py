
from sqlalchemy import text
from sqlalchemy.engine import Connection


class PedidoDetalleRepository:
    """
    Repositorio encargado de las operaciones sobre los detalles
    de los pedidos de proveedor.

    Recibe una conexión SQLAlchemy activa.
    No administra transacciones ni realiza commit/rollback.
    """

    def __init__(self, connection: Connection):
        self.connection = connection

    def insertar_detalle_pedido(self, datos_detalle: dict) -> int:
        """
        Inserta un producto en el detalle del pedido.

        Retorna la cantidad de filas afectadas.
        """

        sql = text("""
            INSERT INTO pddo_prdcto (
                nmro_pddo,
                cdgo_plu,
                cntdad_pdda,
                tpo_lmpza,
                prcio_cmpra,
                prcio_mnda,
                lclzcion,
                nmro_lte
            )
            VALUES (
                :numero_pedido,
                :codigo_plu,
                :cantidad_pedida,
                :nivel,
                :precio,
                :precio_us,
                :localizacion,
                :numero_lote
            )
        """)

        parametros = {
            "numero_pedido": datos_detalle["numero_pedido"],
            "codigo_plu": datos_detalle["codigo_plu"],
            "cantidad_pedida": datos_detalle["cantidad_pedida"],
            "nivel": datos_detalle["nivel"],
            "precio": datos_detalle["precio"],
            "precio_us": datos_detalle["precio_us"],
            "localizacion": datos_detalle["localizacion"],
            "numero_lote": datos_detalle["numero_lote"],
        }

        resultado = self.connection.execute(sql, parametros)

        return resultado.rowcount

    def actualizar_detalle_pedido(self, datos_detalle: dict) -> int:
        """
        Actualiza un detalle identificado por:
        número de pedido + PLU + nivel de limpieza.
        """

        sql = text("""
            UPDATE pddo_prdcto
            SET
                cntdad_pdda = :cantidad_pedida,
                prcio_cmpra = :precio,
                prcio_mnda = :precio_us,
                lclzcion = :localizacion
            WHERE nmro_pddo = :numero_pedido
              AND cdgo_plu = :codigo_plu
              AND tpo_lmpza = :nivel
        """)

        parametros = {
            "cantidad_pedida": datos_detalle["cantidad_pedida"],
            "precio": datos_detalle["precio"],
            "precio_us": datos_detalle["precio_us"],
            "localizacion": datos_detalle["localizacion"],
            "numero_pedido": datos_detalle["numero_pedido"],
            "codigo_plu": datos_detalle["codigo_plu"],
            "nivel": datos_detalle["nivel"],
        }

        resultado = self.connection.execute(sql, parametros)

        return resultado.rowcount

    def eliminar_detalle_pedido(
        self,
        numero_pedido: int,
        codigo_plu: int,
        nivel: int
    ) -> int:
        """
        Elimina un detalle mediante su clave compuesta.
        """

        sql = text("""
            DELETE FROM pddo_prdcto
            WHERE nmro_pddo = :numero_pedido
              AND cdgo_plu = :codigo_plu
              AND tpo_lmpza = :nivel
        """)

        parametros = {
            "numero_pedido": numero_pedido,
            "codigo_plu": codigo_plu,
            "nivel": nivel,
        }

        resultado = self.connection.execute(sql, parametros)

        return resultado.rowcount

    def obtener_detalles_pedido(self, numero_pedido: int) -> list[dict]:
        """
        Consulta todos los detalles asociados a un pedido.
        Retorna una lista de diccionarios.
        """

        sql = text("""
            SELECT
                nmro_pddo,
                cdgo_plu,
                cntdad_pdda,
                tpo_lmpza,
                prcio_cmpra,
                prcio_mnda,
                lclzcion,
                nmro_lte,
                cntdad_rcbda,
                pso_rcbdo,
                lte_prvdor
            FROM pddo_prdcto
            WHERE nmro_pddo = :numero_pedido
        """)

        resultado = self.connection.execute(
            sql,
            {"numero_pedido": numero_pedido}
        )

        return [dict(fila) for fila in resultado.mappings().all()]

    def validar_detalles_pedido(self, numero_pedido: int) -> bool:
        """
        Comprueba si un pedido tiene al menos un detalle.
        """

        sql = text("""
            SELECT TOP 1 1 AS existe
            FROM pddo_prdcto
            WHERE nmro_pddo = :numero_pedido
        """)

        resultado = self.connection.execute(
            sql,
            {"numero_pedido": numero_pedido}
        )

        return resultado.first() is not None
