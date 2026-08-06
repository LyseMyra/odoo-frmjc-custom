from odoo import models, fields


class MobilityRateTravel(models.Model):
    _name = 'mobility.rate.travel'
    _description = 'Barème voyage par tranche kilométrique'
    _order = 'sequence'

    # ── Tranche ──────────────────────────────────────────────────────
    # Les clés reprennent les valeurs BAND_XX attendues par l'export BM.
    # BAND_09/11/30/40/50 sont confirmées par un échantillon BM réel ;
    # BAND_20/60/70 sont des codes PROVISOIRES (km et montants officiels
    # confirmés par le guide Erasmus+, mais code exact non encore vérifié
    # sur un export BM réel pour ces 3 tranches) — à valider avant tout
    # export officiel (Phase 10).
    tranche_kilometrique = fields.Selection(
        selection=[
            ('BAND_09', '0-9 km (non éligible)'),
            ('BAND_11', '10-99 km'),
            ('BAND_20', '100-499 km (code provisoire)'),
            ('BAND_30', '500-1999 km'),
            ('BAND_40', '2000-2999 km'),
            ('BAND_50', '3000-3999 km'),
            ('BAND_60', '4000-7999 km (code provisoire)'),
            ('BAND_70', '8000 km et plus (code provisoire)'),
        ],
        string='Tranche kilométrique',
        required=True,
    )
    sequence = fields.Integer(string='Séquence', default=10)
    montant_standard = fields.Float(string='Montant standard (€)', required=True, digits=(10, 2))
    montant_ecoresponsable = fields.Float(
        string='Montant transport écoresponsable (€)', required=True, digits=(10, 2),
    )

    _unique_tranche = models.Constraint(
        'UNIQUE(tranche_kilometrique)',
        'Un barème existe déjà pour cette tranche kilométrique.'
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = dict(
                rec._fields['tranche_kilometrique'].selection
            ).get(rec.tranche_kilometrique, '?')
