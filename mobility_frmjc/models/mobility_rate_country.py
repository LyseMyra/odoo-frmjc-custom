from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MobilityRateCountry(models.Model):
    _name = 'mobility.rate.country'
    _description = "Barème pays (soutien organisationnel / inclusion / argent de poche)"
    _order = 'country_id, date_debut_validite desc'

    # ── Pays et période de validité ──────────────────────────────────
    country_id = fields.Many2one(
        'res.country',
        string="Pays d'accueil de l'activité",
        help="Pays où se déroule l'activité — pas le pays d'origine du "
             "volontaire. Laisser vide pour le barème générique "
             "« Pays tiers voisin de l'UE », utilisé en repli quand aucun "
             "barème spécifique n'existe pour le pays de mission.",
    )
    date_debut_validite = fields.Date(string='Date de début de validité', required=True)
    date_fin_validite = fields.Date(
        string='Date de fin de validité',
        help='Laisser vide si toujours en vigueur — un barème peut changer '
             "d'un appel à projets à l'autre.",
    )

    # ── Taux journaliers (€/jour) ──────────────────────────────────
    taux_soutien_organisationnel = fields.Float(
        string='Soutien organisationnel (A1)', required=True, digits=(10, 2),
    )
    taux_soutien_inclusion = fields.Float(
        string="Soutien à l'inclusion (A2)", required=True, digits=(10, 2),
        help="Applicable uniquement si le participant est marqué « Jeune »."
    )
    taux_argent_poche = fields.Float(
        string='Argent de poche (A3)', required=True, digits=(10, 2),
    )

    # ── Contraintes ────────────────────────────────────────────────
    @api.constrains('date_debut_validite', 'date_fin_validite')
    def _check_dates(self):
        for rec in self:
            if (rec.date_fin_validite and
                    rec.date_fin_validite <= rec.date_debut_validite):
                raise ValidationError(
                    'La date de fin de validité doit être postérieure à la '
                    'date de début.'
                )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                rec.country_id.name if rec.country_id
                else "Pays tiers voisin de l'UE"
            )
