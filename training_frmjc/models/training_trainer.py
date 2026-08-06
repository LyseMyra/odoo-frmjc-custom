from odoo import models, fields, api


class TrainingTrainer(models.Model):
    _name = 'training.trainer'
    _description = 'Intervenant affecté à une session (convention / type)'
    _order = 'session_id, contact_id'
    _rec_name = 'contact_id'

    # ── Relations principales ──────────────────────────────────────
    contact_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        domain=[],
    )
    session_id = fields.Many2one(
        'training.session',
        string='Session',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employé (si intervenant interne)',
        help='Lien optionnel vers la fiche employé pour les intervenants internes salariés FRMJC',
    )

    # ── Type d'intervenant ─────────────────────────────────────────
    type_intervenant = fields.Selection(
        selection=[
            ('interne', 'Interne'),
            ('externe', 'Prestataire externe'),
        ],
        string='Type',
        required=True,
        default='externe',
    )

    # ── Jours d'intervention ───────────────────────────────────────
    week_line_ids = fields.Many2many(
        'training.week.line',
        string='Jours d\'intervention',
        domain="[('session_id', '=', session_id)]",
    )
    nb_jours_intervention = fields.Integer(
        string='Nombre de jours d\'intervention',
        compute='_compute_nb_jours',
    )

    # ── Convention de prestation ───────────────────────────────────
    convention_prestation_id = fields.Many2one(
        'training.document',
        string='Convention de prestation liée',
    )
    statut_convention = fields.Selection(
        selection=[
            ('non_requise', 'Non requise'),
            ('generee', 'Générée'),
            ('envoyee', 'Envoyée pour signature'),
            ('signee', 'Signée'),
        ],
        string='Statut de la convention',
        default='non_requise',
    )

    # ── Contraintes SQL ────────────────────────────────────────────
    _contact_session_unique = models.Constraint(
        'UNIQUE(contact_id, session_id)',
        'Cet intervenant est déjà affecté à cette session.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('contact_id').write({'is_formateur': True})
        return records

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('week_line_ids')
    def _compute_nb_jours(self):
        for rec in self:
            rec.nb_jours_intervention = len(rec.week_line_ids)

    # ── Logique métier ─────────────────────────────────────────────
    @api.onchange('type_intervenant')
    def _onchange_type_intervenant(self):
        if self.type_intervenant == 'interne':
            self.statut_convention = 'non_requise'
        elif self.type_intervenant == 'externe':
            if self.statut_convention == 'non_requise':
                self.statut_convention = False

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            type_label = dict(
                rec._fields['type_intervenant'].selection
            ).get(rec.type_intervenant, '')
            rec.display_name = f'{rec.contact_id.name} ({type_label})' if rec.contact_id else '?'
