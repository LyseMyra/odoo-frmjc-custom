from odoo import models, fields, api


class TrainingModule(models.Model):
    _name = 'training.module'
    _description = 'Module du référentiel pédagogique'
    _order = 'bloc_id, sequence, intitule'
    _rec_name = 'intitule'

    # ── Identification ─────────────────────────────────────────────
    intitule = fields.Char(
        string='Intitulé',
        required=True,
    )
    code = fields.Char(
        string='Code',
        help='Référence interne optionnelle (ex : M1.1, M2.3, BAT1)',
    )
    bloc_id = fields.Many2one(
        'training.bloc',
        string='Bloc (BC / BAT)',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Ordre', default=10)

    # ── Champs liés (pour filtres et affichage) ────────────────────
    formation_id = fields.Many2one(
        related='bloc_id.formation_id',
        string='Formation',
        store=True,
        readonly=True,
    )
    type_bloc = fields.Selection(
        related='bloc_id.type_bloc',
        string='Type de bloc',
        store=True,
        readonly=True,
    )

    # ── Objectifs et contenu ────────────────────────────────────────
    objectifs = fields.Text(string='Objectifs de formation')
    contenus = fields.Text(string='Contenus')
    modalites_peda = fields.Text(
        string='Modalités pédagogiques',
        help='Ex : Apports théoriques, travaux de groupe, études de cas…',
    )

    # ── Entreprise / alternance ────────────────────────────────────
    activites_entreprise = fields.Text(
        string='Activités à réaliser en entreprise',
        help='Ce que le/la stagiaire doit faire en situation de travail',
    )
    commandes_tuteur = fields.Text(
        string='Commandes pour le MA / Tuteur',
        help='Instructions adressées au maître d\'apprentissage ou tuteur',
    )

    # ── Intervenant par défaut ─────────────────────────────────────
    intervenant_default_id = fields.Many2one(
        'res.partner',
        string='Intervenant par défaut',
        domain=[('is_company', '=', False)],
    )

    # ── Volumes horaires ───────────────────────────────────────────
    volume_of = fields.Float(
        string='Volume OF (h)',
        help='Heures en organisme de formation',
    )
    volume_entreprise = fields.Float(
        string='Volume entreprise (h)',
        help='Heures totales consacrées en entreprise',
    )
    volume_total = fields.Float(
        string='Total (h)',
        compute='_compute_volume_total',
        store=True,
        help='Volume OF + Volume entreprise',
    )

    # ── Répartition hebdomadaire ───────────────────────────────────
    repartition_ids = fields.One2many(
        'training.module.repartition', 'module_id',
        string='Répartition (semaine / jour / heures)',
    )

    # ── Fenêtre de placement — calculée depuis la répartition ─────
    semaine_debut = fields.Integer(
        string='S° début',
        compute='_compute_semaines_range',
        store=True,
    )
    semaine_fin = fields.Integer(
        string='S° fin',
        compute='_compute_semaines_range',
        store=True,
    )

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('volume_of', 'volume_entreprise')
    def _compute_volume_total(self):
        for rec in self:
            rec.volume_total = (rec.volume_of or 0.0) + (rec.volume_entreprise or 0.0)

    # ── Méthodes compute ───────────────────────────────────────────
    @api.depends('repartition_ids.semaine')
    def _compute_semaines_range(self):
        for rec in self:
            semaines = rec.repartition_ids.mapped('semaine')
            rec.semaine_debut = min(semaines) if semaines else 0
            rec.semaine_fin = max(semaines) if semaines else 0

    # ── Représentation ─────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'[{rec.code}] {rec.intitule}' if rec.code else (rec.intitule or '?')

