from odoo import models, fields, api


class TrainingBloc(models.Model):
    _name = 'training.bloc'
    _description = "Bloc de compétences (BC) ou Bloc d'Accompagnement Transversal (BAT)"
    _order = 'formation_id, sequence, name'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────
    name = fields.Char(
        string='Code',
        required=True,
        help='Ex : BC1, BC2, BAT1, BC1-2-3-4',
    )
    intitule = fields.Char(string='Intitulé / UF')
    type_bloc = fields.Selection(
        selection=[
            ('bc', 'Bloc de Compétences (BC)'),
            ('bat', "Bloc d'Accompagnement Transversal (BAT)"),
            ('transversal', 'Modules transversaux (multi-BC)'),
        ],
        string='Type',
        required=True,
        default='bc',
    )
    formation_id = fields.Many2one(
        'training.formation',
        string='Formation',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Ordre', default=10)

    # ── Modules ────────────────────────────────────────────────────
    module_ids = fields.One2many(
        'training.module',
        'bloc_id',
        string='Modules',
    )
    nb_modules = fields.Integer(
        string='Nb modules',
        compute='_compute_nb_modules',
        store=True,
    )

    # ── Contraintes SQL ────────────────────────────────────────────
    _unique_bloc = models.Constraint(
        'UNIQUE(name, formation_id)',
        'Un bloc avec ce code existe déjà pour cette formation.',
    )

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('module_ids')
    def _compute_nb_modules(self):
        for rec in self:
            rec.nb_modules = len(rec.module_ids)

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.name} – {rec.intitule}' if rec.intitule else (rec.name or '?')
