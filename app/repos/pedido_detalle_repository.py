
from sqlalchemy import text
from sqlalchemy.engine import Connection
import socket

#nombre_equipo = socket.gethostname()
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
    
    def _precio_historico(self, codigo_proveedor: int, codigo_plu: int) -> float:
        """Último precio registrado para proveedor + producto. 0 si no hay."""

        # OPCIÓN A: usar tu función existente (descomenta una según donde esté)
        # from app.repos.proveedores_repository import precio_proveedor      # función suelta
        # return float(precio_proveedor(self.connection, codigo_proveedor, codigo_plu) or 0)
        #
        # from app.repos.catalogos_repository import CatalogosRepository     # método de otra clase
        # return float(CatalogosRepository.precio_proveedor(codigo_proveedor, codigo_plu) or 0)

        # OPCIÓN B: consulta propia, en la misma transacción (activa por ahora)
        sql = text("""
            SELECT TOP 1 prcio_cmpra
            FROM vrcnes_prvdor
            WHERE idntfccion = :proveedor
              AND cdgo_plu = :plu
            ORDER BY fcha_incia DESC, fcha_rprte DESC
        """)
        valor = self.connection.execute(
            sql, {"proveedor": codigo_proveedor, "plu": codigo_plu}
        ).scalar()
        return float(valor or 0)
    
    def registrar_variacion_precio(
        self,
        codigo_proveedor: int,
        codigo_plu: int,
        precio: float,
        fecha_pedido,
        fecha_servidor,
        operador: str,
        estado: int = 1,   # CONFIRMAR: valor de estdo para un precio vigente
    ) -> bool:
        """
        Registra en vrcnes_prvdor el cambio de precio de un producto de un proveedor.

        Solo inserta si el último precio histórico es > 0 y distinto del nuevo.
        Usa la misma conexión (transacción) del repositorio.
        Retorna True si insertó un registro, False si no hubo nada que registrar.
        """

        precio_nuevo = float(precio)

        # CONFIRMAR: firma de precio_proveedor(). Si es una función del módulo
        # que recibe la conexión, usa: precio_proveedor(self.connection, ...)
        precio_historico = self._precio_historico(codigo_proveedor, codigo_plu)
        
        print(f"el precio historico obtenido es :{precio_historico}")
        # Sin histórico válido: se conserva el comportamiento actual.
        if precio_historico <= 0:
            return False

        # Mismo precio: no hay variación que registrar.
        if round(precio_historico, 4) == round(precio_nuevo, 4):
            return False

        sql = text("""
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
                :proveedor,
                :plu,
                :fecha_inicia,
                :precio,
                :estado,
                :fecha_reporte,
                :operador
            )
        """)

        resultado = self.connection.execute(sql, {
            "proveedor": codigo_proveedor,
            "plu": codigo_plu,
            "fecha_inicia": fecha_pedido,
            "precio": precio_nuevo,
            "estado": estado,
            "fecha_reporte": fecha_servidor,
            "operador": operador,
        })

        return resultado.rowcount == 1
