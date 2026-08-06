from odoo import models, fields, api


class TrainingRubanWizardSemaine(models.TransientModel):
    _name = 'training.ruban.wizard.semaine'
    _description = 'Semaine candidate dans le wizard de ruban'
    _order = 'numero_semaine'

    wizard_id = fields.Many2one(
        'training.ruban.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )

    numero_semaine = fields.Integer(string='N° semaine')
    date_debut = fields.Date(string='Date de début')
    date_fin = fields.Date(string='Date de fin')

    statut_propose = fields.Selection(
        selection=[
            ('a_statut_libre', 'Statut libre'),
            ('exclue_auto', 'Exclue automatiquement (jour férié)'),
        ],
        string='Statut détecté',
        readonly=True,
    )
    
    contient_jour_ferie = fields.Boolean(
        string='Contient un jour férié',
        default=False,
        readonly=True,
    )

    selectionnee = fields.Boolean(string='Sélectionnée')
    type_semaine = fields.Selection(
        selection=[
            ('formation', 'Semaine de formation'),
            ('certification', 'Certification d\'un BC'),
            ('remediation', 'Remédiation d\'un BC'),
            ('rencontre_tuteurs', 'Rencontre tuteurs'),
            ('animation', 'Animation temps de formation'),
            ('autre', 'Autre'),
        ],
        string='Type',
        default='formation',
    )
    # Pour les non-formation (certifications, etc.) : date précise de l'événement
    # Si renseigné, date_debut = date_fin = cette date dans training.week
    date_jour = fields.Date(
        string='Date (si journée)',
        help='Pour une certification ou un événement ponctuel : '
             'indiquez la date exacte de la journée (dans la semaine détectée). '
             'Laissez vide pour une semaine de formation.',
    )
    motif_exclusion = fields.Char(string='Motif (si exclusion manuelle)')
    
    mois_annee = fields.Char(
        string='Mois',
        compute='_compute_mois_annee',
    )

    @api.depends('date_debut')
    def _compute_mois_annee(self):
        for rec in self:
            if rec.date_debut:
                rec.mois_annee = rec.date_debut.strftime('%B %Y')
            else:
                rec.mois_annee = ''