from odoo import models, fields, api
from odoo.exceptions import ValidationError
import zipfile
import pandas as pd
from io import BytesIO
from io import StringIO
import base64
import re
import chardet
import tempfile
import datetime

class ModeloDMS(models.Model):
    _name = 'modelo.dms'
    _description = 'Modelo DMS'

    nombre_dms = fields.Char(string="Nombre del DMS", required=True)
    activo = fields.Boolean(string="Activo", default=True)
    es_favorito = fields.Boolean("Es Favorito")
    reporte_ids = fields.One2many('reporte.dms', 'dms_id', string="Reportes")
    report_count = fields.Integer(string="Número de Reportes", compute="_compute_report_count")


    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.nombre_dms))
        return result

    def action_open_reports(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Crear Reporte DMS',
            'view_mode': 'tree,form',
            'res_model': 'reporte.dms',
            'target': 'current',
            'domain': [('nombre_dms_origen', '=', self.nombre_dms)],
            'context': {'default_nombre_dms_origen': self.nombre_dms} 
        }

    @api.depends('reporte_ids')
    def _compute_report_count(self):
        for record in self:
            record.report_count = len(record.reporte_ids)


class FormulasReportes(models.Model):
    _name = 'formulas.reportes'
    _description = 'Formulas Reportes'

    reporte_id = fields.Many2one('reporte.dms', string="Reporte DMS")
    columnas_reporte_ids = fields.Many2many('reporte.dms.detalle', compute="_compute_columnas_reporte")
    expresion = fields.Text(string="Expresión")
    cliente = fields.Integer(string='Número de Cliente')
    branch = fields.Char(string='Branch')

    tabla_html = fields.Html(string='Tabla Procesada')

    @api.depends('reporte_id')
    def _compute_columnas_reporte(self):
        for record in self:
            if record.reporte_id:
                record.columnas_reporte_ids = [(6, 0, record.reporte_id.detalle_ids.ids)]
            else:
                record.columnas_reporte_ids = [(5,)]

    def action_add_columna_to_expresion(self):
        # Obtener el ID de la columna desde el contexto
        columna_id = self.env.context.get('columna_id')
        if columna_id:
            columna = self.env['reporte.dms.detalle'].browse(columna_id).columna
            # Si existe la columna, añadirla a la expresión
            for record in self:
                if columna:
                    if record.expresion:
                        record.expresion += f" {columna}"
                    else:
                        record.expresion = columna
    

    def action_procesar(self):
        # Obtener el cliente y branch del registro actual
        cliente_num = self.cliente
        branch = self.branch
        reporte_dms = self.reporte_id.nombre  # Nombre del reporte
        print(f'reporte_dms: {reporte_dms}')

        # Buscar en cliente.configuracion si tiene ZIP cargado para el cliente y branch
        cliente_config = self.env['cliente.configuracion'].search([
            ('num_cliente', '=', cliente_num),
            ('branch', '=', branch)
        ], limit=1)

        if not cliente_config or not cliente_config.archivo_zip:
            # Mostrar un mensaje si no hay ZIP cargado
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Advertencia',
                    'message': f'No hay archivo ZIP cargado para el cliente {cliente_num} y branch {branch}.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            # Decodificar el contenido del archivo ZIP desde Base64
            zip_file_content = base64.b64decode(cliente_config.archivo_zip)  # Decodifica el archivo ZIP cargado

            # Leer el archivo ZIP desde el contenido binario decodificado
            zipfile_obj = zipfile.ZipFile(BytesIO(zip_file_content))

            print(f'Zip_obj: {zipfile_obj}')

        except zipfile.BadZipFile:
            # Manejo del error en caso de que no sea un archivo ZIP válido
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error de archivo',
                    'message': 'El archivo cargado no es un ZIP válido. Por favor, cargue un archivo ZIP válido.',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        found_file = None
        pattern = re.sub(r'\d', '', reporte_dms)  # Elimina todos los números del nombre del reporte
        print(f'Pattern: {pattern}')

        for file_name in zipfile_obj.namelist():
            # Elimina números del nombre de archivo y compara solo las letras
            file_name_no_digits = re.sub(r'\d', '', file_name)
            print(f'File_name: {file_name_no_digits}')
            
            if pattern in file_name_no_digits:
                found_file = file_name
                break

        if not found_file:
            # Mostrar una alerta si no se encuentra el reporte dentro del ZIP
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'No se encontró el reporte {reporte_dms} en el ZIP cargado para el cliente {cliente_num} y branch {branch}.',
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        print("Vamos armar el DF")
        print(f'Found_file: {found_file}')


        # Leer el contenido del archivo encontrado en el ZIP
        with zipfile_obj.open(found_file) as file:
            print(f'File: {file}')
            
            # Leer el contenido del archivo
            rawdata = file.read()
            
            # Detectar la codificación del archivo
            result = chardet.detect(rawdata)
            encoding = result['encoding']
            
            # Decodificar el archivo con la codificación detectada
            file_content = rawdata.decode(encoding, errors='replace')  # Manejar errores de codificación
            
            # Crear un archivo temporal CSV
            with tempfile.NamedTemporaryFile(mode='w+', newline='', delete=False, suffix=".csv") as temp_csv:
                # Escribir el contenido en el archivo temporal
                temp_csv.write(file_content)
                temp_csv.seek(0)  # Asegúrate de volver al inicio del archivo antes de leerlo

                # Leer el archivo CSV temporal con pandas, ignorando errores
                try:
                    df = pd.read_csv(temp_csv.name, delimiter='|', encoding=encoding, on_bad_lines='skip', header=None)
                except Exception as e:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Error',
                            'message': f'Error al leer el archivo: {str(e)}',
                            'type': 'danger',
                            'sticky': False,
                        }
                    }


        # Obtener las columnas del DataFrame y crear los encabezados de la tabla
        columnas = [col.columna for col in self.columnas_reporte_ids]
        print(f'Columnas: {columnas}')

        # Verificar si la última columna está completamente vacía y eliminarla
        if df.columns[-1] == '' or df[df.columns[-1]].isnull().all():
            df = df.iloc[:, :-1]  # Elimina la última columna vacía

        # Verificar el número de columnas en el DataFrame
        print(f'Número de columnas del DataFrame: {len(df.columns)}')
        print(f'Número de columnas esperadas: {len(columnas)}')

        # Asegurarse de que la cantidad de columnas coincida
        if len(df.columns) != len(columnas):
            raise ValueError(f'Error: El número de columnas en el DataFrame ({len(df.columns)}) no coincide con el número esperado de columnas ({len(columnas)}).')

        # Asignar tus propias columnas
        df.columns = columnas
        print(f'DF: {df}')

        df = df.drop(0).reset_index(drop=True)
        # Mostrar los primeros 3 registros para validar
        df_head = df.head(3)
        print(df_head)

        # Filtrar el DataFrame para solo mostrar las columnas relevantes
        df_filtered = df[columnas]

        # Mostrar los primeros 3 registros en la vista del formulario
        table_html = df_filtered.head(3).to_html(classes='table table-bordered', border=0, index=False).replace("\n", "")

        # Reemplazar y agregar estilos directamente al HTML generado
        table_html = table_html.replace(
            '<table border="0" class="dataframe table table-bordered">',
            '<table style="width: 100%; table-layout: fixed; border-collapse: collapse;" class="table">'
        ).replace(
            '<th>', '<th style="width: 200px; padding: 8px; text-align: left; white-space: nowrap;">'
        ).replace(
            '<td>', '<td style="width: 200px; padding: 8px; text-align: left; white-space: nowrap;">'
        )

        # Guardar el contenido HTML de la tabla en el campo 'tabla_html'
        self.write({'tabla_html': table_html})


        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reporte procesado',
                'message': f'Reporte {reporte_dms} procesado correctamente.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'}
            }
        }


    def aplicar_formula(self):
        # Obtener el DataFrame actual desde la tabla procesada
        df = self.obtener_dataframe()
        if df is None:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'No se pudo obtener el DataFrame.',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        # Extraer las columnas del DataFrame
        columnas = [col.columna for col in self.columnas_reporte_ids]

        # Convertir la fórmula del usuario
        formula = self.expresion.strip()

        # Validar que la fórmula tenga contenido
        if not formula:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error en la fórmula',
                    'message': 'La fórmula no puede estar vacía.',
                    'type': 'danger',
                    'sticky': False,
                }
            }

        # Aplicar la fórmula con eval
        try:
            # Reemplazar las columnas con su representación en pandas (df['Columna'])
            for columna in columnas:
                formula = formula.replace(columna, f"df['{columna}']")

            # Aplicar el eval directamente a la columna en cuestión
            # Suponemos que la fórmula afecta una única columna y se evalúa en toda la serie
            for columna in columnas:
                if columna in formula:
                    df[columna] = eval(formula)  # Evalúa la fórmula y la aplica a la columna
                    break

            # Actualizar el campo 'tabla_html' con el DataFrame procesado
            table_html = df.to_html(classes='table table-bordered', border=0).replace("\n", "")

            # Reemplazar y agregar estilos directamente al HTML generado
            table_html = table_html.replace(
                '<table border="0" class="dataframe table table-bordered">', 
                '<table style="width: 100%; table-layout: fixed; border-collapse: collapse;" class="table">'
            ).replace(
                '<th>', '<th style="width: 200px; padding: 8px; text-align: left; white-space: nowrap;">'
            ).replace(
                '<td>', '<td style="width: 200px; padding: 8px; text-align: left; white-space: nowrap;">'
            )

            # Guardar el contenido HTML de la tabla en el campo 'tabla_html'
            self.write({'tabla_html': table_html})

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Éxito',
                    'message': 'Fórmula aplicada correctamente.',
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'}
                }
            }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error al aplicar la fórmula',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }



    def obtener_dataframe(self):
        """
        Función para obtener el DataFrame actual utilizando las columnas dinámicas
        y validar que coincidan con el reporte procesado.
        """
        try:
            # Obtener las columnas dinámicas definidas en el reporte
            columnas = [col.columna for col in self.columnas_reporte_ids]
            print(f'Columnas dinámicas: {columnas}')
            
            # Leer el archivo CSV desde la tabla actual en HTML
            # Esto simula obtener el contenido del DataFrame desde la tabla procesada previamente
            raw_html = self.tabla_html  # Obtener el HTML de la tabla

            if not raw_html:
                raise ValueError("No se ha procesado la tabla previamente.")

            # Extraer el contenido del HTML a un DataFrame
            dfs = pd.read_html(raw_html)  # Convertir la tabla HTML de vuelta a un DataFrame
            if len(dfs) == 0:
                raise ValueError("No se pudo extraer un DataFrame válido del HTML.")
            
            df = dfs[0]  # Tomar el primer DataFrame

            # Verificar si la última columna está completamente vacía y eliminarla
            if df.columns[-1] == '' or df[df.columns[-1]].isnull().all():
                df = df.iloc[:, :-1]  # Eliminar la última columna vacía si todas sus celdas son nulas

            # Verificar el número de columnas en el DataFrame
            print(f'Número de columnas en el DataFrame: {len(df.columns)}')
            print(f'Número de columnas esperadas: {len(columnas)}')

            # Asegurarse de que la cantidad de columnas coincida
            if len(df.columns) != len(columnas):
                raise ValueError(f'Error: El número de columnas en el DataFrame ({len(df.columns)}) no coincide con el número esperado de columnas ({len(columnas)}).')

            # Asignar las columnas dinámicas al DataFrame
            df.columns = columnas
            print(f'DataFrame procesado:\n{df.head()}')

            return df

        except Exception as e:
            print(f'Error obteniendo el DataFrame dinámico: {str(e)}')
            return None




class FiltrosReportes(models.Model):
    _name = 'filtros.reportes'
    _description = 'Filtros Reportes'

    name = fields.Char()


from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ReporteDMS(models.Model):
    _name = 'reporte.dms'
    _description = 'Reporte DMS'

    nombre = fields.Char(string="Nombre del Reporte", required=True, index=True)
    nombre_dms_origen = fields.Char(string="Nombre DMS Origen", readonly=True)
    detalle_ids = fields.One2many('reporte.dms.detalle', 'reporte_id', string="Detalles")
    count_detalle_ids = fields.Integer("Cantidad de Detalles", compute='_compute_count_detalle_ids')
    dms_id = fields.Many2one('modelo.dms', string="DMS")

    # Modificada para validar el nombre del reporte dentro del mismo nombre_dms_origen
    @api.model
    def create(self, vals):
        print(f'vals: {vals}')
        # Asegurarse de que se tenga 'nombre_dms_origen' correctamente
        nombre_dms_origen = vals.get('nombre')
        print(f'Nombredmsorigen: {nombre_dms_origen}')
        if not nombre_dms_origen:
            dms = self.env['modelo.dms'].browse(vals['dms_id'])
            nombre_dms_origen = dms.nombre_dms if dms else None
            vals['nombre_dms_origen'] = nombre_dms_origen

        if vals.get('nombre') and nombre_dms_origen:
            # Buscar existentes con el mismo nombre y nombre_dms_origen
            existing = self.search([
                ('nombre', '=', vals['nombre']),
                ('nombre_dms_origen', '=', nombre_dms_origen)
            ])
            if existing:
                raise ValidationError("El nombre del reporte debe ser único dentro del mismo origen DMS.")

        return super(ReporteDMS, self).create(vals)
    

    # @api.model
    # def create(self, vals):
    #     # Obtener el nombre_dms_origen del contexto si no está en vals
    #     nombre_dms_origen = vals.get('nombre_dms_origen', self.env.context.get('default_nombre_dms_origen'))
    #     print(f'Nombre_dms_origen: {nombre_dms_origen}')
    #     if nombre_dms_origen:
    #         dms = self.env['modelo.dms'].search([('nombre_dms', '=', nombre_dms_origen)], limit=1)
    #         if dms:
    #             vals['dms_id'] = dms.id
    #             vals['nombre_dms_origen'] = nombre_dms_origen  # Asegúrate de que este campo se establezca si es necesario

    #     return super(ReporteDMS, self).create(vals)

    def write(self, vals):
        if 'nombre' in vals or 'nombre_dms_origen' in vals:
            nombre = vals.get('nombre', self.nombre)
            nombre_dms_origen = vals.get('nombre_dms_origen', self.nombre_dms_origen)
            existing = self.search([
                ('nombre', '=', nombre),
                ('nombre_dms_origen', '=', nombre_dms_origen),
                ('id', '!=', self.id)
            ])
            if existing:
                raise ValidationError("El nombre del reporte debe ser único dentro del mismo origen DMS.")
        return super(ReporteDMS, self).write(vals)

    @api.depends('detalle_ids')
    def _compute_count_detalle_ids(self):
        for record in self:
            record.count_detalle_ids = len(record.detalle_ids)

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.nombre))
        return result

    def action_open_formulas(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Formulas',
            'view_mode': 'tree,form',
            'res_model': 'formulas.reportes',
            'target': 'current',
            'context': {'default_reporte_id': self.id}
        }

    def action_open_filter(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Filtros',
            'view_mode': 'tree,form',
            'res_model': 'filtros.reportes',
            'target': 'current'
        }


class ReportesDMS(models.Model):
    _name = 'reportes.dms'
    _description = 'Reportes DMS'

    nombre_reporte = fields.Char(string="Nombre del Reporte", required=True)
    descripcion = fields.Text(string="Descripción")
    nombre_dms_origen = fields.Char(string="Nombre DMS Origen", readonly=True) 


class ReporteDMSDetalle(models.Model):
    _name = 'reporte.dms.detalle'
    _description = 'Detalle de Reporte DMS'
    _order = 'sequence'

    reporte_id = fields.Many2one('reporte.dms', string="Reporte", required=True, ondelete='cascade')
    ordenamiento = fields.Char(string="Ordenamiento", compute='_compute_ordenamiento', store=True)
    columna = fields.Char(string="Columna")
    tipo_dato = fields.Selection([
        ('double presicion', 'Double Presicion'),
        ('date', 'Date'),
        ('character varying', 'Character Varying')
    ], string="Tipo de Dato")
    longitud = fields.Integer(string="Longitud", default=0)
    invisible = fields.Boolean(string="Invisible", default=False)
    sequence = fields.Integer(string="Secuencia")
    expresion = fields.Html(string="Expresión", sanitize=False, strip_style=False)



    @api.model
    def create(self, vals):
        # Verificar si la columna ya existe para el mismo ID de reporte
        if 'columna' in vals and 'reporte_id' in vals:
            existing = self.env['reporte.dms.detalle'].search([
                ('columna', '=', vals['columna']),
                ('reporte_id', '=', vals['reporte_id'])
            ], limit=1)
            if existing:
                raise ValidationError("La columna '{}' ya está en uso para el mismo reporte.".format(vals['columna']))

        # Asignar la secuencia pero solo dentro del mismo reporte
        if 'reporte_id' in vals:
            last_detail = self.env['reporte.dms.detalle'].search([
                ('reporte_id', '=', vals['reporte_id'])
            ], order='sequence desc', limit=1)
            next_sequence = (last_detail.sequence + 1) if last_detail else 1
            vals['sequence'] = next_sequence

        # Crear el registro
        record = super(ReporteDMSDetalle, self).create(vals)

        # Asegurarse de que el campo ordenamiento se calcula correctamente
        record._compute_ordenamiento()

        return record


    
    @api.constrains('columna', 'reporte_id')
    def _check_columna(self):
        for record in self:
            # Asegurarte de que 'reporte_id' contiene un ID y no un recordset.
            reporte_id = record.reporte_id.id if record.reporte_id else False
            domain = [('columna', '=', record.columna), ('reporte_id', '=', reporte_id), ('id', '!=', record.id)]
            existing = self.search(domain, limit=1)
            if existing:
                raise ValidationError("La columna '{}' ya está en uso para el reporte actual.".format(record.columna))


    def action_add_columna_to_expresion(self):
        # Obtener el ID de la columna desde el contexto
        columna_id = self.env.context.get('columna_id')
        if columna_id:
            columna = self.env['reporte.dms.detalle'].browse(columna_id).columna
            # Si existe la columna, añadirla a la expresión
            for record in self:
                if columna:
                    if record.expresion:
                        record.expresion += f" {columna}"
                    else:
                        record.expresion = columna


    @api.depends('sequence')
    def _compute_ordenamiento(self):
        for record in self:
            record.ordenamiento = f'F{record.sequence}'

    @api.onchange('tipo_dato')
    def _onchange_tipo_dato(self):
        if self.tipo_dato != 'character varying':
            self.longitud = 0
        else:
            self.longitud = 255  # Establece un valor predeterminado si se requiere
    
