from odoo import models, fields


class TrainingInscriptionExperience(models.Model):
    _name = 'training.inscription.experience'
    _description = "Expérience déclarée par un candidat"
    _order = 'inscription_id, sequence, id'

    inscription_id = fields.Many2one(
        'training.inscription', string='Dossier',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(string='Séquence', default=10)
    annee_periode = fields.Char(string='Année / Période', required=True)
    heures = fields.Float(string="Nombre d'heures effectuées", required=True)
    structure = fields.Char(string='Nom de la structure', required=True)
    fonction = fields.Char(string='Fonction', required=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = ' — '.join(filter(None, (
                rec.annee_periode, rec.structure, rec.fonction,
            ))) or 'Expérience'
