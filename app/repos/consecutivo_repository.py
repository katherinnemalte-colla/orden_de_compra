
"""
Descripción:
    Administra la obtención de consecutivos para los pedidos
    a proveedores mediante procedimientos almacenados de SQL Server.

Responsabilidades:
    - Solicitar consecutivos a SQL Server.
    - Obtener el número generado mediante un parámetro OUTPUT.
    - Validar que el consecutivo retornado sea válido.

"""

from sqlalchemy import text
from sqlalchemy.engine import Connection


class ConsecutivoRepository:

    def __init__(self, connection: Connection):

        self.connection = connection

    def obtener_consecutivo_pedido(self) -> int:
        """
        Obtiene el siguiente consecutivo para pedidos a proveedores.

        Procedimiento almacenado:
            dbo.CONSECUTIVO_SQL_OBTENER

        Parámetros enviados al procedimiento:

            @cTabla:
                PDDOS_PRVDOR.
                Identifica el contador en la tabla cnsctvo_tblas.

            @cTablaEva:
                pddos_prvdor.
                Tabla real donde se verifica la existencia del pedido.

            @cCampoEva:
                nmro_pddo.
                Campo donde se valida que el consecutivo no exista.

            @cProceso:
                10.
                Identificador del proceso de pedidos a proveedores.

            @nUltimo:
                Parámetro OUTPUT que devuelve el consecutivo generado.

        Retorna:
            int:
                Número consecutivo disponible para el pedido.

        Excepciones:
            ValueError:
                Si SQL Server retorna un consecutivo igual a cero,
                negativo o nulo.

            Exception:
                Si ocurre un error durante la ejecución SQL.
        """

        sql = text("""
            DECLARE @nUltimo INT;

            EXEC dbo.CONSECUTIVO_SQL
                @cTabla = :tabla,
                @cTablaEva = :tabla_evaluar,
                @cCampoEva = :campo_evaluar,
                @cProceso = :proceso,
                @nUltimo = @nUltimo OUTPUT;

            SELECT @nUltimo AS consecutivo;
        """)

        # Parámetros enviados al procedimiento almacenado.
        parametros = {
            "tabla": "PDDOS_PRVDOR",
            "tabla_evaluar": "pddos_prvdor",
            "campo_evaluar": "nmro_pddo",
            "proceso": 10
        }

        # Ejecutar el procedimiento almacenado.
        resultado = self.connection.execute(sql, parametros)

        # Recuperar el consecutivo retornado por SQL Server.
        registro = resultado.fetchone()

        # Validar que SQL Server haya retornado información.
        if registro is None:
            raise ValueError(
                "No fue posible obtener el consecutivo del pedido."
            )

        # Convertir el resultado a entero.
        consecutivo = registro.consecutivo

        if consecutivo is None or int(consecutivo) <= 0:
            raise ValueError(
                "SQL Server no generó un consecutivo válido para el pedido."
            )

        # Retornar el consecutivo generado.
        return int(consecutivo)
