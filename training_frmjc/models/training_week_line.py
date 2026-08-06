from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class TrainingWeekLine(models.Model):
    _name = 'training.week.line'
    _description = 'Affectation d\'un module à un jour de la semaine'
    _order = 'week_id, jour'
    _rec_name = 'module_id'

    # ── Relations principales ──────────────────────────────────────
    week_id = fields.Many2one(
        'training.week',
        string='Semaine',
        required=True,
        ondelete='cascade',
    )
    module_id = fields.Many2one(
        'training.module',
        string='Module',
        required=True,
        ondelete='restrict',
    )

    # ── Jour et volume ─────────────────────────────────────────────
    jour = fields.Selection(
        selection=[
            ('lundi', 'Lundi'),
            ('mardi', 'Mardi'),
            ('mercredi', 'Mercredi'),
            ('jeudi', 'Jeudi'),
            ('vendredi', 'Vendredi'),
        ],
        string='Jour',
        required=True,
    )
    heures = fields.Float(
        string='Heures',
        required=True,
    )
    heure_debut = fields.Float(
        string='Heure de début',
        digits=(4, 2),
        help='Heure de début du module (ex : 9.0 = 9h00, 14.5 = 14h30). Optionnel.',
    )

    date_jour = fields.Date(
        string='Date du jour',
        compute='_compute_date_jour',
        store=True,
    )

    # ── Intervenant effectif ───────────────────────────────────────
    intervenant_id = fields.Many2one(
        'res.partner',
        string='Intervenant effectif',
        help='Intervenant affecté à ce jour.',
    )

    # ── Champs liés (lecture facile) ───────────────────────────────
    session_id = fields.Many2one(
        related='week_id.session_id',
        string='Session',
        store=True,
    )

    # ── Contraintes SQL ────────────────────────────────────────────
    _check_heures_positive = models.Constraint(
        'CHECK(heures > 0)',
        'Le nombre d\'heures doit être positif.'
    )

    # ── Contraintes Python ─────────────────────────────────────────
    @api.constrains('week_id', 'jour', 'heures')
    def _check_total_jour(self):
        for rec in self:
            lines_meme_jour = self.search([
                ('week_id', '=', rec.week_id.id),
                ('jour', '=', rec.jour),
                ('id', '!=', rec.id),
            ])
            total = sum(lines_meme_jour.mapped('heures')) + rec.heures
            if total > 10:
                raise ValidationError(
                    f'Le total d\'heures pour {rec.jour} '
                    f'({total}h) dépasse 10h, ce qui semble anormal. '
                    f'Vérifiez la saisie.'
                )

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.jour}: {rec.module_id.code} ({rec.heures}h)' if rec.module_id else '?'
    

    @api.depends('week_id.date_debut', 'jour')
    def _compute_date_jour(self):
        jours_offset = {
            'lundi': 0, 'mardi': 1, 'mercredi': 2,
            'jeudi': 3, 'vendredi': 4,
        }
        for rec in self:
            if rec.week_id.date_debut and rec.jour:
                rec.date_jour = rec.week_id.date_debut + timedelta(
                    days=jours_offset.get(rec.jour, 0)
                )
            else:
                rec.date_jour = False