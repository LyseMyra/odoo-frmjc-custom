from odoo import models, fields


class TrainingInscriptionDocument(models.Model):
    _name = 'training.inscription.document'
    _description = "Document justificatif complémentaire d'un dossier d'inscription"
    _order = 'inscription_id, sequence, id'

    inscription_id = fields.Many2one(
        'training.inscription', string='Dossier',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Séquence', default=10)
    name = fields.Char(string='Nature du document', required=True)
    fichier = fields.Binary(string='Fichier', attachment=True, required=True)
    fichier_filename = fields.Char()

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or rec.fichier_filename or 'Document'
