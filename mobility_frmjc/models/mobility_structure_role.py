from odoo import models, fields


class MobilityStructureRole(models.Model):
    _name = 'mobility.structure.role'
    _description = "Rôle d'une structure partenaire (volontariat)"
    _order = 'sequence, name'

    name = fields.Char(string='Rôle', required=True, translate=True)
    code = fields.Char(
        string='Code',
        required=True,
        help='Identifiant technique stable (utilisé pour les filtres/domaines).',
    )
    sequence = fields.Integer(string='Séquence', default=10)

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Ce code de rôle existe déjà.'
    )
