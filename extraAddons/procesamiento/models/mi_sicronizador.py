from odoo import models, fields, api
import json
from odoo.exceptions import ValidationError

class SincronizadorReportes(models.Model):
    _name = 'sincronizador.reportes'
    _description = 'Sincronizador de Reportes de Clientes'

    def generar_json(self):
        # Inicializamos la estructura final del JSON
        registros = []

        # Obtenemos todas las configuraciones de clientes
        clientes_config = self.env['cliente.configuracion'].search([])

        # Iteramos sobre cada cliente configurado
        for cliente in clientes_config:
            sucursal_data = {
                "sucursal": cliente.nombre,  # Nombre de la sucursal/cliente
                "branch": cliente.branch,  # Branch del cliente
                "dms": {}  # Inicializamos la estructura de DMS
            }

            # Obtenemos los DMS configurados para este cliente
            dms_config = cliente.dms_id

            # Iteramos sobre los DMS y agrupamos los reportes por DMS
            if dms_config:
                for dms in dms_config:
                    # Inicializamos la lista de reportes por DMS
                    reportes_dms = []

                    # Obtenemos los reportes asociados al DMS actual
                    reportes = self.env['reporte.dms'].search([('dms_id', '=', dms.id)])

                    # Agregamos los nombres de los reportes al array de reportes del DMS
                    for reporte in reportes:
                        reportes_dms.append(reporte.nombre)

                    # Asignamos los reportes a la clave DMS en sucursal_data
                    sucursal_data["dms"][dms.nombre_dms] = reportes_dms

            # Añadimos la sucursal con sus DMS y reportes al array de registros
            registros.append(sucursal_data)

        # Estructura final
        json_final = {
            "registros": registros
        }

        # Convertimos el diccionario a JSON
        json_string = json.dumps(json_final, indent=4)

        # Puedes retornar el JSON para que lo puedas guardar o visualizar
        return json_string

    # Acción del botón para generar el JSON
    def action_generar_json(self):
        json_resultado = self.generar_json()
        # Aquí puedes hacer algo con el JSON generado, por ejemplo, guardarlo en un archivo o mostrarlo
        raise ValidationError(f'JSON Generado: {json_resultado}')
