from odoo import models, fields


class TrainingExpense(models.Model):
    _name = 'training.expense'
    _description = 'Dépense liée à une certification'
    _order = 'date_depense desc'

    certification_id = fields.Many2one(
        'training.certification', required=True, ondelete='cascade', index=True,
    )
    session_id = fields.Many2one(
        related='certification_id.session_id', store=True, readonly=True, string='Session',
    )
    type_depense = fields.Selection([
        ('honoraires_jury', 'Honoraires jury'),
        ('deplacement',     'Déplacement'),
        ('salle',           'Location de salle'),
        ('materiel',        'Matériel'),
        ('autre',           'Autre'),
    ], required=True, default='autre', string='Type')
    description = fields.Char(string='Description', required=True)
    montant = fields.Float(string='Montant (€)', required=True, digits=(10, 2))
    statut = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide',    'Validée'),
        ('rembourse', 'Remboursée'),
    ], default='brouillon', required=True)
    date_depense = fields.Date(string='Date', default=fields.Date.today)
    justificatif = fields.Binary(string='Justificatif', attachment=True)
    justificatif_filename = fields.Char()

    def action_valider(self):
        self.write({'statut': 'valide'})

    def action_rembourser(self):
        self.write({'statut': 'rembourse'})
