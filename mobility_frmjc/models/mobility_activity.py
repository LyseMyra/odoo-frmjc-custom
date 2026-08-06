from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MobilityActivity(models.Model):
    _name = 'mobility.activity'
    _description = 'Activité / offre de mobilité'
    _order = 'code_activite'

    # ── Identification ─────────────────────────────────────────────
    name = fields.Char(string='Nom activité', required=True)
    code_activite = fields.Char(
        string='Code activité',
        required=True,
        help="Ex : A01 à A22. Partagé par toutes les mobilités d'une même "
             "activité (mobilité en équipe, mêmes dates/lieu) — un même code "
             "n'est jamais dupliqué sur plusieurs fiches.",
    )
    id_lieu = fields.Char(
        string='ID lieu (BM)',
        help="Identifiant technique du lieu dans l'export BM (souvent \"1\" "
             "pour les accueils FRMJC / FDMJC22).",
    )
    domaine = fields.Char(
        string='Domaine',
        help="Thématique de la mission — ex : Inclusion & Diversité.",
    )
    description = fields.Text(string='Description')
    # offer_code (ID offre BM) n'est PAS un champ de l'activité : il est
    # individuel par mobilité même au sein d'une même activité partagée
    # (règle §18.6 du cahier, confirmée par l'échantillon BM). Il sera
    # ajouté sur mobility.mobility en Phase 5.

    # ── Classification ────────────────────────────────────────────
    programme = fields.Selection(
        selection=[
            ('sc', 'Service Civique (SC)'),
            ('ces', 'Corps Européen de Solidarité (CES)'),
            ('vsi', 'Volontariat Service International (VSI)'),
        ],
        string='Programme',
        required=True,
    )

    # ── Structure et lieu ───────────────────────────────────────────
    hosting_partner_id = fields.Many2one(
        'res.partner',
        string="Structure d'accueil",
        domain=[('structure_role_ids.code', '=', 'accueil')],
    )
    country_id = fields.Many2one('res.country', string="Pays d'accueil")
    city = fields.Char(string="Ville de l'activité")

    # ── Dates ──────────────────────────────────────────────────────
    start_date = fields.Date(string='Date de début (proposée)')
    end_date = fields.Date(string='Date de fin (proposée)')

    # ── Contraintes ────────────────────────────────────────────────
    _unique_code_activite = models.Constraint(
        'UNIQUE(code_activite)',
        'Une activité avec ce code existe déjà.'
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date <= rec.start_date:
                raise ValidationError(
                    'La date de fin doit être postérieure à la date de début.'
                )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f'{rec.code_activite} — {rec.name}' if rec.name else rec.code_activite
            )
