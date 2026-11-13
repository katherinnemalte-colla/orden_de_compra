
from app.repos.pedidos_repository import (
    buscar_numeros,
    cargar_pedido
)

from app.repos.catalogos_repository import CatalogosRepository

class PedidosService:
    @classmethod
    def obtener_catalogos(cls) -> dict:
        """Obtiene los catálogos necesarios para el formulario."""
        return {
            "proveedores": CatalogosRepository.proveedores(),
            "niveles": CatalogosRepository.niveles_limpieza(),
            "bodegas": CatalogosRepository.bodegas(),
        }


    @classmethod
    def preparar_nuevo(cls) -> dict:
        """
        Prepara el formulario para crear una nueva solicitud.
        No realiza inserciones ni modificaciones en BD.
        """
        datos = cls.obtener_catalogos()

        datos.update({
            "modo": "nuevo",

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
        })

        return datos
    
    @classmethod
    def preparar_consulta(cls, numero_pedido: int) -> dict:
        """Prepara los datos de un pedido para mostrarlo en pantalla."""

        pedido = cargar_pedido(numero_pedido)

        if not pedido:
            return None

        cab = pedido["cabecera"]
        lineas = pedido["lineas"]

        datos = cls.obtener_catalogos()

        datos.update({
            "modo": "consulta",

            # Cabecera
            "c": {
                "estdo": cab["estdo"],
                "estado": cab["estado_nombre"],
                "prov": cab["idntfccion"],
                "fped": cab["fcha_pddo"],
                "fpac": cab["fcha_pctda"],
                "internacional": cab["tpo_ped"],
                "oc": cab["orden_cmpra_int"],
                "lote": cab["lte_int"],
                "trm": cab["trm"],
                "bod": cab["bdga_dstno"],
                "reg": cab["realizado"],
            },

            # Producto seleccionado
            "sel": {
                "plu": "",
                "nombre": "",
                "nivel": "",
                "precio": None,
                "us": None,
            },

            # Líneas del pedido
            "lineas": [
                {
                    "plu": ln["cdgo_plu"],
                    "nombre": ln["nmbre_prdcto"],
                    "bod": ln["lclzcion"],
                    "nivel": ln["tpo_lmpza"],
                    "qty": ln["cntdad_pdda"],
                    "precio": ln["prcio_cmpra"],
                    "us": ln["prcio_mnda"],
                    "sel": False,
                    "url": "#",
                }
                for ln in lineas
            ],

            "bars": [],
            "steps": [],
            "cost": 0,
            "margin": 0,
            "total_iva": 0,
        })

        return datos