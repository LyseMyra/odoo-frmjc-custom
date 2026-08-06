from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MobilityGrant(models.Model):
    _name = 'mobility.grant'
    _description = 'Convention de subvention (grant Erasmus+)'
    _order = 'date_debut desc'
    _rec_name = 'numero_convention'

    # ── Identification ─────────────────────────────────────────────
    numero_convention = fields.Char(
        string='Numéro de convention',
        required=True,
        help="Ex : 2024-1-FR02-ESC51-VTJ-000199813 — identifie le grant "
             "Erasmus annuel.",
    )
    programme = fields.Selection(
        selection=[
            ('sc', 'Service Civique (SC)'),
            ('ces', 'Corps Européen de Solidarité (CES)'),
            ('vsi', 'Volontariat Service International (VSI)'),
        ],
        string='Programme',
        required=True,
    )

    # ── Période de validité ────────────────────────────────────────
    date_debut = fields.Date(string='Date de début', required=True)
    date_fin = fields.Date(string='Date de fin', required=True)

    # ── Mobilités rattachées ───────────────────────────────────────
    mobility_ids = fields.One2many(
        'mobility.mobility', 'grant_id', string='Mobilités rattachées',
    )
    nb_mobilities = fields.Integer(
        string='Nb mobilités', compute='_compute_nb_mobilities',
    )

    # ── Contraintes ────────────────────────────────────────────────
    _unique_numero_convention = models.Constraint(
        'UNIQUE(numero_convention)',
        'Une convention de subvention avec ce numéro existe déjà.'
    )

    @api.depends('mobility_ids')
    def _compute_nb_mobilities(self):
        for rec in self:
            rec.nb_mobilities = len(rec.mobility_ids)

    @api.constrains('date_debut', 'date_fin')
    def _check_dates(self):
        for rec in self:
            if rec.date_debut and rec.date_fin and rec.date_fin <= rec.date_debut:
                raise ValidationError(
                    'La date de fin doit être postérieure à la date de début.'
                )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            label = dict(rec._fields['programme'].selection).get(rec.programme, '')
            rec.display_name = (
                f'{rec.numero_convention} ({label})' if label else rec.numero_convention
            )
