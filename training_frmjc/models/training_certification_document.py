from odoo import models, fields


class TrainingCertificationDocument(models.Model):
    _name = 'training.certification.document'
    _description = 'Document de certification'
    _order = 'date_depot desc'

    certification_id = fields.Many2one(
        'training.certification', required=True, ondelete='cascade', index=True,
    )
    type_document = fields.Selection([
        ('dossier_validation', 'Dossier de validation'),
        ('grille_evaluation',  "Grille d'évaluation"),
        ('attestation',        'Attestation'),
        ('rapport_jury',       'Rapport de jury'),
        ('autre',              'Autre'),
    ], required=True, default='autre', string='Type')
    nom = fields.Char(string='Nom du document', required=True)
    fichier = fields.Binary(string='Fichier', attachment=True)
    fichier_filename = fields.Char()
    date_depot = fields.Date(string='Date de dépôt', default=fields.Date.today)
    notes = fields.Text(string='Notes')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.nom or '?'
