from odoo import models


class TrainingInscription(models.Model):
    _inherit = 'training.inscription'

    def action_generer_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'template.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': self._name,
                'active_id': self.id,
            },
        }
