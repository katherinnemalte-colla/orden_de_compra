
import logging
import os
from app.conexion import Conexion
from app.repos.pedido_repository import PedidoRepository
from app.repos import pedidos_repository
from app.repos.pedido_detalle_repository import PedidoDetalleRepository
from app.repos.consecutivo_repository import ConsecutivoRepository
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ProductoDuplicado(ValueError):
        """El PLU (con ese nivel) ya está en el pedido."""
class PedidoService:
    @staticmethod
    def es_pendiente(estado) -> bool:
        return estado not in PedidoService.ESTADOS_NO_PENDIENTES
    
    @staticmethod
    def _operador(usuario: str, terminal: str = "") -> str:
        """Mismo formato que 'REGISTRADO POR': usuario - terminal."""
        return f"{usuario} - {terminal}" if terminal else str(usuario)

    @staticmethod
    def _fecha_servidor(connection):
        return connection.execute(text("SELECT GETDATE()")).scalar_one()
    
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
    def crear_pedido(datos_pedido: dict, detalles: list[dict], terminal: str = "") -> dict:

        # 1. Copiar y completar ANTES de validar.
        cabecera = datos_pedido.copy()
        lista_detalles = [detalle.copy() for detalle in detalles]

        cabecera.setdefault("usuario", os.getenv("APP_USUARIO", "SIN-LOGIN"))
        cabecera.setdefault("lote_interno", None)
        cabecera.setdefault("trm", 0)

        for detalle in lista_detalles:
            detalle.setdefault("precio_us", 0)
            detalle.setdefault("numero_lote", None)
            detalle["localizacion"] = cabecera.get("bodega_destino")

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
                if filas != 1:
                    raise RuntimeError(f"No fue posible insertar el PLU {detalle['codigo_plu']}.")

                # Historial de precios (solo cantidad > 0)
                if float(detalle["cantidad_pedida"]) > 0:
                    detalle_repo.registrar_variacion_precio(
                        codigo_proveedor=cabecera["codigo_proveedor"],
                        codigo_plu=detalle["codigo_plu"],
                        precio=detalle["precio"],
                        fecha_pedido=cabecera["fecha_pedido"],
                        fecha_servidor=cabecera["fecha_servidor"],   # el GETDATE() que ya obtienes
                        operador=PedidoService._operador(cabecera["usuario"], terminal),
                    )
        return {
            "exito": True,
            "mensaje": "Pedido creado correctamente.",
            "numero_pedido": numero_pedido,
            "total_productos": len(lista_detalles),
        }
        
    @staticmethod
    def actualizar_detalle_pedido(datos_detalle: dict, terminal: str = "") -> int:
        numero_pedido = int(datos_detalle["numero_pedido"])

        pedido = pedidos_repository.cargar_pedido(numero_pedido)
        if pedido is None:
            raise ValueError("El pedido no existe.")

        cab = pedido["cabecera"]
        if not PedidoService.es_pendiente(cab["estdo"]):
            raise ValueError("Solo se pueden modificar pedidos en estado Pendiente.")


        try:
            logger.info(
                "Datos recibidos para actualizar el detalle. "
                "Pedido: %s | PLU: %s | Nivel: %s",
                datos_detalle.get("numero_pedido"),
                datos_detalle.get("codigo_plu"),
                datos_detalle.get("nivel"),
            )

            campos_actualizar = (
                "cantidad_pedida",
                "precio",
                "precio_us",
                "localizacion",
            )

            campos_identificacion = (
                "numero_pedido",
                "codigo_plu",
                "nivel",
            )

            # 1. Validar campos requeridos.
            logger.info("Validando campos requeridos.")

            campos_requeridos = campos_actualizar + campos_identificacion

            faltantes = [
                campo
                for campo in campos_requeridos
                if campo not in datos_detalle
            ]

            if faltantes:
                logger.warning(
                    "Validación fallida. Campos faltantes: %s",
                    ", ".join(faltantes),
                )
                raise ValueError(
                    f"Faltan campos para actualizar el detalle: {', '.join(faltantes)}"
                )

            logger.info("Validación de campos requeridos completada.")

            # 2. Validar identificadores.
            logger.info("Validando identificadores del detalle.")

            if not datos_detalle["numero_pedido"]:
                logger.warning("El número de pedido está vacío.")
                raise ValueError("El número de pedido es obligatorio.")

            if not datos_detalle["codigo_plu"]:
                logger.warning("El código PLU está vacío.")
                raise ValueError("El código PLU es obligatorio.")

            if datos_detalle["nivel"] is None:
                logger.warning("El nivel de limpieza es nulo.")
                raise ValueError("El nivel de limpieza es obligatorio.")

            logger.info(
                "Identificadores validados correctamente. "
                "Pedido: %s | PLU: %s | Nivel: %s",
                datos_detalle["numero_pedido"],
                datos_detalle["codigo_plu"],
                datos_detalle["nivel"],
            )

            # 3. Iniciar transacción.
            logger.info("Iniciando transacción con la base de datos.")

            with Conexion.transaccion() as connection:

                logger.info("Conexión y transacción iniciadas correctamente.")

                # 4. Instanciar repositorio.
                logger.info("Instanciando PedidoDetalleRepository.")

                detalle_repo = PedidoDetalleRepository(connection)

                # 5. Ejecutar actualización.
                logger.info(
                    "Ejecutando actualización. Pedido: %s | PLU: %s | Nivel: %s",
                    datos_detalle["numero_pedido"],
                    datos_detalle["codigo_plu"],
                    datos_detalle["nivel"],
                )

                filas = detalle_repo.actualizar_detalle_pedido(datos_detalle)

                logger.info(
                    "Resultado de actualización. Filas afectadas: %s",
                    filas,
                )

                # 6. Validar resultado.
                if filas == 0:
                    logger.warning(
                        "No se encontró el detalle. "
                        "Pedido: %s | PLU: %s | Nivel: %s",
                        datos_detalle["numero_pedido"],
                        datos_detalle["codigo_plu"],
                        datos_detalle["nivel"],
                    )

                    raise ValueError(
                        "No se encontró el producto del pedido que se desea actualizar."
                    )
                    
                if filas and float(datos_detalle["cantidad_pedida"]) > 0:
                   detalle_repo.registrar_variacion_precio(
                        codigo_proveedor=cab["idntfccion"],
                        codigo_plu=int(datos_detalle["codigo_plu"]),
                        precio=datos_detalle["precio"],
                        fecha_pedido=cab["fcha_pddo"],
                        fecha_servidor=PedidoService._fecha_servidor(connection),
                        operador=PedidoService._operador(os.getenv("APP_USUARIO", "SIN-LOGIN"), terminal),
                    )

                logger.info(
                    "Detalle actualizado correctamente. "
                    "Pedido: %s | PLU: %s | Filas afectadas: %s",
                    datos_detalle["numero_pedido"],
                    datos_detalle["codigo_plu"],
                    filas,
                )

                logger.info("========== FIN ACTUALIZACIÓN DETALLE PEDIDO ==========")

                return filas

        except ValueError as e:
            logger.warning(
                "Validación o actualización no realizada: %s",
                str(e),
            )
            raise

        except Exception:
            logger.exception(
                "Error inesperado durante la actualización del detalle del pedido."
            )
            raise

    # Igual que _clase_estado() en vistas.py: 9 anulado, 3 y 4 recibido; el resto, pendiente.
    ESTADOS_NO_PENDIENTES = (3, 4, 9)

    @staticmethod
    def _norm_bodega(valor) -> str:
        """'01', ' 1 ' y 1 se consideran la misma bodega."""
        texto = str(valor if valor is not None else "").strip()
        return texto.lstrip("0") or ("0" if texto else "")

    @staticmethod
    def agregar_detalle(numero_pedido: int, detalle: dict) -> dict:
        """
        RF-04: agrega una línea a un pedido pendiente.
        - La bodega del pedido se asigna al producto.
        - Si ya existe producto + nivel + bodega, se ACTUALIZA en lugar de duplicar.
        """
        d = detalle.copy()
        d.setdefault("precio_us", 0)
        d.setdefault("numero_lote", None)

        PedidoService._validar_detalles([d])

        datos = pedidos_repository.cargar_pedido(numero_pedido)
        if datos is None:
            raise ValueError("El pedido no existe.")

        cab = datos["cabecera"]
        if not PedidoService.es_pendiente(cab["estdo"]):
            raise ValueError(
                "Solo se pueden agregar productos a pedidos en estado Pendiente."
            )

        # La bodega elegida en el pedido se asigna a todos los productos.
        bodega = cab["bdga_dstno"]
        d["localizacion"] = bodega
        d["numero_pedido"] = numero_pedido

        plu = int(d["codigo_plu"])
        nivel = str(d["nivel"]).strip()
        clave_bodega = PedidoService._norm_bodega(bodega)

        # ¿Ya existe la misma línea? producto + nivel + bodega
        existente = next(
            (
                f for f in datos["lineas"]
                if int(f["cdgo_plu"]) == plu
                and str(f["tpo_lmpza"]).strip() == nivel
                and PedidoService._norm_bodega(f["lclzcion"]) == clave_bodega
            ),
            None,
        )

        if existente is not None:
            # Actualizar en lugar de duplicar.
            filas = PedidoService.actualizar_detalle_pedido({
                "numero_pedido": numero_pedido,
                "codigo_plu": plu,
                "nivel": int(d["nivel"]),
                "cantidad_pedida": d["cantidad_pedida"],
                "precio": d["precio"],
                "precio_us": d["precio_us"],
                "localizacion": existente["lclzcion"],   # tal como está guardada
            })
            logger.info("Línea actualizada | pedido=%s plu=%s nivel=%s filas=%r",
                        numero_pedido, plu, nivel, filas)
            if filas == 0:
                raise RuntimeError(f"No fue posible actualizar el PLU {plu}.")
            return {"exito": True, "accion": "actualizado", "numero_pedido": numero_pedido}

        # No existe: insertar.
        with Conexion.transaccion() as connection:
            filas = PedidoDetalleRepository(connection).insertar_detalle_pedido(d)
            logger.info("Línea agregada | pedido=%s plu=%s nivel=%s filas=%r",
                        numero_pedido, plu, nivel, filas)
            if filas != 1:
                raise RuntimeError(f"No fue posible insertar el PLU {plu}.")

        return {"exito": True, "accion": "agregado", "numero_pedido": numero_pedido}
    
    @staticmethod
    def eliminar_detalle(datos: dict) -> int:
        """Elimina una línea de un pedido pendiente. Devuelve las filas afectadas."""
        datos_pedido = pedidos_repository.cargar_pedido(int(datos["numero_pedido"]))
        if datos_pedido is None:
            raise ValueError("El pedido no existe.")

        if not PedidoService.es_pendiente(datos_pedido["cabecera"]["estdo"]):
            raise ValueError(
                "Solo se pueden eliminar productos de pedidos en estado Pendiente."
            )

        with Conexion.transaccion() as connection:
            filas = PedidoDetalleRepository(connection).eliminar_detalle_pedido(
            int(datos["numero_pedido"]),
            codigo_plu=int(datos["codigo_plu"]),
            nivel=int(datos["nivel"]),
            )
            #filas = PedidoDetalleRepository(connection).eliminar_detalle_pedido(datos)
            logger.info("Detalle eliminado | pedido=%s filas=%r", datos["numero_pedido"], filas)

        return filas