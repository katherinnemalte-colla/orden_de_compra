
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
    
    def registrar_variacion_precio(self, datos_precio: dict) -> int:
        """
        Registra una variación de precio en vrcnes_prvdor.

        Reglas de negocio:
        1. Consulta el último precio del proveedor y PLU.
        2. Si el precio histórico es mayor que cero,
           compara contra el precio nuevo.
        3. Si son diferentes, inserta un nuevo registro.
        4. Si no existe precio histórico positivo o los
           precios son iguales, no inserta.

        No administra transacciones.
        Retorna 1 si insertó y 0 si no insertó.
        """

        # 1. Consultar el último precio histórico
        sql_consulta = text("""
            SELECT TOP 1 prcio_cmpra
            FROM vrcnes_prvdor
            WHERE idntfccion = :codigo_proveedor
              AND cdgo_plu = :codigo_plu
              AND fcha_incia <= :fecha_actual
            ORDER BY fcha_incia DESC
        """)

        parametros_consulta = {
            "codigo_proveedor": datos_precio["codigo_proveedor"],
            "codigo_plu": datos_precio["codigo_plu"],
            "fecha_actual": datos_precio["fecha_actual"],
        }

        resultado = self.connection.execute(
            sql_consulta,
            parametros_consulta
        ).scalar_one_or_none()

        # 2. Validar que exista un precio histórico positivo
        if resultado is None or resultado <= 0:
            return 0

        precio_anterior = resultado
        precio_nuevo = datos_precio["precio"]

        # 3. Comparar el precio histórico con el nuevo
        if precio_anterior == precio_nuevo:
            return 0

        # 4. Insertar la variación de precio
        sql_insert = text("""
            INSERT INTO vrcnes_prvdor (
                idntfccion,
                cdgo_plu,
                fcha_incia,
                prcio_cmpra,
                estdo,
                fcha_rprte,
                oprdor
            )
            VALUES (
                :codigo_proveedor,
                :codigo_plu,
                :fecha_pedido,
                :precio,
                2,
                :fecha_reporte,
                :operador
            )
        """)

        parametros_insert = {
            "codigo_proveedor": datos_precio["codigo_proveedor"],
            "codigo_plu": datos_precio["codigo_plu"],
            "fecha_pedido": datos_precio["fecha_pedido"],
            "precio": precio_nuevo,
            "fecha_reporte": datos_precio["fecha_reporte"],
            "operador": datos_precio["operador"],
        }

        resultado_insert = self.connection.execute(
            sql_insert,
            parametros_insert
        )

        return resultado_insert.rowcount
