
from app.repos.pedidos import CatalogosRepository


class PedidosService:

    @classmethod
    def preparar_nuevo(cls) -> dict:
        """
        Prepara el formulario para crear una nueva solicitud.
        No realiza inserciones ni modificaciones en BD.
        """

        return {
            "modo_nuevo": True,

            # Catálogos
            "proveedores": CatalogosRepository.proveedores(),
            "niveles": CatalogosRepository.niveles_limpieza(),
            "bodegas": CatalogosRepository.bodegas(),

            # Cabecera del pedido
            "c": {
                "estdo": None,
                "estado": "",
                "prov": "",
                "fped": "",
                "fpac": "",
                "internacional": False,
                "oc": "",
                "lote": "",
                "trm": None,
                "bod": "",
                "reg": "",
            },

            # Producto seleccionado
            "sel": {
                "plu": "",
                "nombre": "",
                "nivel": "",
                "precio": None,
                "us": None,
            },

            # Líneas y resumen
            "lineas": [],
            "bars": [],
            "steps": [],
            "cost": 0,
            "margin": 0,
            "total_iva": 0,
        }
