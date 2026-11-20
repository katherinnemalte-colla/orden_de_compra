
import logging
import os
from app.conexion import Conexion
from app.repos.pedido_repository import PedidoRepository
from app.repos.pedido_detalle_repository import PedidoDetalleRepository
from app.repos.consecutivo_repository import ConsecutivoRepository
from sqlalchemy import text
logger = logging.getLogger(__name__)
class PedidoService:
    
    @staticmethod
    def _validar_cabecera(datos: dict) -> None:
        """
        Comprueba que la cabecera tenga los datos necesarios
        para que el repositorio pueda insertarla.
        """

        campos_obligatorios = [
            "codigo_proveedor",
            "fecha_pedido",
            "fecha_pactada",
            "tipo_pedido",
            "bodega_destino"
        ]

        for campo in campos_obligatorios:
            if campo not in datos or datos[campo] is None:
                raise ValueError(
                    f"El campo {campo} es obligatorio."
                )

    @staticmethod
    def _validar_detalles(detalles: list[dict]) -> None:
        """
        Valida que:
        - Exista al menos un producto.
        - Cada producto tenga PLU, nivel, cantidad y precio.
        - La cantidad sea mayor que cero.
        - No se repita la combinación PLU + nivel.
        """

        if not detalles:
            raise ValueError(
                "El pedido debe contener al menos un producto."
            )

        combinaciones = set()

        for detalle in detalles:

            campos_obligatorios = [
                "codigo_plu",
                "cantidad_pedida",
                "nivel",
                "precio"
            ]

            for campo in campos_obligatorios:
                if campo not in detalle or detalle[campo] is None:
                    raise ValueError(
                        f"Falta el campo {campo} en un producto."
                    )

            # Validar que la cantidad sea numérica y positiva.
            try:
                cantidad = float(detalle["cantidad_pedida"])
            except (TypeError, ValueError):
                raise ValueError(
                    f"La cantidad del PLU {detalle['codigo_plu']} "
                    "no es válida."
                )

            if cantidad <= 0:
                raise ValueError(
                    f"La cantidad del PLU {detalle['codigo_plu']} "
                    "debe ser mayor que cero."
                )

            # Validar que el precio sea numérico.
            try:
                float(detalle["precio"])
                float(detalle.get("precio_us", 0))
            except (TypeError, ValueError):
                raise ValueError(
                    f"El precio del PLU {detalle['codigo_plu']} "
                    "no es válido."
                )

            # Evitar duplicados según la clave utilizada
            # actualmente por UPDATE y DELETE.
            try:
                clave = (
                    int(detalle["codigo_plu"]),
                    int(detalle["nivel"])
                )
            except (TypeError, ValueError):
                raise ValueError(
                    "El PLU y el nivel de limpieza deben ser válidos."
                )

            if clave in combinaciones:
                raise ValueError(
                    f"El PLU {clave[0]} está repetido "
                    f"con el nivel de limpieza {clave[1]}."
                )

            combinaciones.add(clave)

    @staticmethod
    def crear_pedido(datos_pedido: dict, detalles: list[dict]) -> dict:

        # 1. Copiar y completar ANTES de validar.
        cabecera = datos_pedido.copy()
        lista_detalles = [detalle.copy() for detalle in detalles]

        cabecera.setdefault("usuario", os.getenv("APP_USUARIO", "SIN-LOGIN"))
        cabecera.setdefault("lote_interno", None)
        cabecera.setdefault("trm", 0)

        for detalle in lista_detalles:
            detalle.setdefault("precio_us", 0)
            detalle.setdefault("localizacion", None)
            detalle.setdefault("numero_lote", None)

        # 2. Validar (con los datos ya completos).
        PedidoService._validar_cabecera(cabecera)
        PedidoService._validar_detalles(lista_detalles)

        # 3. Transacción.
        with Conexion.transaccion() as connection:

            logger.info("DEBUG 1: transacción abierta")
            consecutivo_repo = ConsecutivoRepository(connection)
            numero_pedido = consecutivo_repo.obtener_consecutivo_pedido()
            logger.info("DEBUG 2: consecutivo = %r", numero_pedido)

            if numero_pedido is None:
                raise RuntimeError("No fue posible obtener el consecutivo del pedido.")

            numero_pedido = int(numero_pedido)   # por si llega como Row/Decimal

            cabecera["numero_pedido"] = numero_pedido
            cabecera["lote_interno"] = 0         # lote fijo (como lo tenías)
            cabecera["fecha_servidor"] = connection.execute(
                text("SELECT GETDATE()")
            ).scalar_one()
            logger.info("DEBUG 3: cabecera lista = %s", cabecera)

            pedido_repo = PedidoRepository(connection)
            detalle_repo = PedidoDetalleRepository(connection)

            filas = pedido_repo.insertar_pedido(cabecera)
            logger.info("DEBUG 4: filas cabecera = %r", filas)
            if filas != 1:
                raise RuntimeError("No fue posible insertar la cabecera del pedido.")

            for detalle in lista_detalles:
                detalle["numero_pedido"] = numero_pedido
                filas = detalle_repo.insertar_detalle_pedido(detalle)
                logger.info("DEBUG 5: filas detalle PLU %s = %r", detalle["codigo_plu"], filas)
                if filas != 1:
                    raise RuntimeError(
                        f"No fue posible insertar el PLU {detalle['codigo_plu']}."
                    )

        return {
            "exito": True,
            "mensaje": "Pedido creado correctamente.",
            "numero_pedido": numero_pedido,
            "total_productos": len(lista_detalles),
        }