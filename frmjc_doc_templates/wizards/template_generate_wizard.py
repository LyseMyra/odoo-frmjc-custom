import base64

from odoo import models, fields, api
from odoo.exceptions import UserError


class TemplateGenerateWizard(models.TransientModel):
    _name = 'template.generate.wizard'
    _description = 'Génération de document depuis un modèle'

    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
    record_name = fields.Char(readonly=True)
    template_id = fields.Many2one(
        'template.document', string='Modèle de document', required=True,
    )
    state = fields.Selection([
        ('choose', 'Choisir'),
        ('done', 'Terminé'),
    ], default='choose')
    file = fields.Binary(string='Document généré', readonly=True)
    file_name = fields.Char(readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        res_model = self.env.context.get('active_model')
        res_id = self.env.context.get('active_id')
        if res_model and 'res_model' in fields_list:
            vals['res_model'] = res_model
        if res_id and 'res_id' in fields_list:
            vals['res_id'] = res_id
        if res_model and res_id:
            record = self.env[res_model].browse(res_id)
            if record.exists():
                vals['record_name'] = record.display_name
            templates = self.env['template.document'].search([
                ('model_name', '=', res_model),
            ])
            if len(templates) == 1 and 'template_id' in fields_list:
                vals['template_id'] = templates.id
        return vals

    def action_generate(self):
        self.ensure_one()
        record = self.env[self.res_model].browse(self.res_id)
        if not record.exists():
            raise UserError("L'enregistrement d'origine est introuvable.")
        content = self.template_id.generate(record)
        filename = f"{self.template_id.name} - {record.display_name}.docx"
        self.write({
            'file': base64.b64encode(content).decode('ascii'),
            'file_name': filename,
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
