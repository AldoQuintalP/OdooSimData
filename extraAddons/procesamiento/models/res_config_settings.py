from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    clients_folder_path = fields.Char(
        string="Ruta de la carpeta CLIENTS",
        config_parameter='my_module.clients_folder_path',
        help="Directorio para almacenar los archivos de clientes.")
    
    working_folder_path = fields.Char(
        string="Ruta de la carpeta 2-Working",
        config_parameter='my_module.working_folder_path',
        help="Directorio para colocar el archivo .zip a procesar.")
    
    sandbox_folder_path = fields.Char(
        string="Ruta de la carpeta 3-Sandbox",
        config_parameter='my_module.sandbox_folder_path',
        help="Directorio para almacer los resultados del procesamiento.")