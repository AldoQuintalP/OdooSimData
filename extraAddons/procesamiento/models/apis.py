import json  # Asegúrate de importar el módulo json
from odoo.http import request, Response
from datetime import datetime
from odoo import http

class ProcesamientoController(http.Controller):
    @http.route('/validate_zip_file', type='http', auth='public', methods=['POST'], csrf=False)
    def validate_zip_file(self, **post):
        try:
            # Obtenemos el archivo desde la petición
            file = request.httprequest.files.get('file')
            print(f'File: {file}')  # Verificar que el archivo llega correctamente
            if not file:
                return Response(json.dumps({'error': 'No se subió ningún archivo.'}), content_type='application/json')

            # Extraer partes del nombre del archivo
            file_name = file.filename
            cliente = file_name[:4].lstrip('0')  # Eliminar ceros a la izquierda
            branch = file_name[4:6]
            current_day = datetime.now().strftime('%d')
            file_day = file_name[6:8]

            # Verificar en la base de datos si el cliente y branch existen
            cliente_config = request.env['cliente.configuracion'].sudo().search([
                ('num_cliente', '=', int(cliente)),
                ('branch', '=', branch)
            ])

            # Verificar la existencia de cliente y branch
            cliente_exists = bool(cliente_config)
            branch_exists = bool(cliente_config)
            is_today = (current_day == file_day)

            # Devolver la respuesta en formato JSON
            return Response(json.dumps({
                'cliente_exists': cliente_exists,
                'branch_exists': branch_exists,
                'is_today': is_today,
                'error': False
            }), content_type='application/json')

        except Exception as e:
            # En caso de error, lo imprimimos en el log y devolvemos un error JSON
            print(f'Error: {e}')
            return Response(json.dumps({
                'error': 'Error en el servidor: ' + str(e)
            }), content_type='application/json')
