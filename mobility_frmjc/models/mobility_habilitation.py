from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MobilityHabilitation(models.Model):
    _name = 'mobility.habilitation'
    _description = 'Habilitation label LEAD (consortium Erasmus+)'
    _order = 'date_obtention desc'
    _rec_name = 'numero_habilitation'

    # ── Identification ─────────────────────────────────────────────
    numero_habilitation = fields.Char(
        string='Numéro d\'habilitation',
        required=True,
        help='Ex : 2021-1-FR02-ESC50-018892',
    )
    organisme_lead_id = fields.Many2one(
        'res.partner',
        string='Organisme LEAD',
        required=True,
        domain=[('structure_role_ids.code', '=', 'consortium_lead')],
        help='Structure partenaire titulaire (LEAD/consortium).',
    )

    # ── Période de validité ────────────────────────────────────────
    date_obtention = fields.Date(string="Date d'obtention", required=True)
    date_expiration = fields.Date(
        string="Date d'expiration",
        required=True,
        help='Validité habituelle ~5 ans.',
    )

    # ── Agence nationale ───────────────────────────────────────────
    agence_nationale_country_id = fields.Many2one(
        'res.country',
        string='Pays agence nationale',
        help="Pays de l'agence nationale Erasmus+ associée à cette "
             "habilitation — déjà encodé dans le numéro d'habilitation "
             "(ex : le « FR » de FR02 dans 2021-1-FR02-ESC50-018892). "
             "Utilisé pour la règle de cohérence §20 du cahier.",
    )

    # ── Mobilités couvertes ─────────────────────────────────────────
    mobility_ids = fields.One2many(
        'mobility.mobility', 'habilitation_id', string='Mobilités couvertes',
    )
    nb_mobilities = fields.Integer(
        string='Nb mobilités', compute='_compute_nb_mobilities',
    )

    # ── Contraintes ────────────────────────────────────────────────
    _unique_numero_habilitation = models.Constraint(
        'UNIQUE(numero_habilitation)',
        'Une habilitation avec ce numéro existe déjà.'
    )

    @api.depends('mobility_ids')
    def _compute_nb_mobilities(self):
        for rec in self:
            rec.nb_mobilities = len(rec.mobility_ids)

    @api.constrains('date_obtention', 'date_expiration')
    def _check_dates(self):
        for rec in self:
            if (rec.date_obtention and rec.date_expiration and
                    rec.date_expiration <= rec.date_obtention):
                raise ValidationError(
                    "La date d'expiration doit être postérieure à la date d'obtention."
                )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f'{rec.numero_habilitation} — {rec.organisme_lead_id.name}'
                if rec.organisme_lead_id else rec.numero_habilitation
            )
