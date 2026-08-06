from odoo import models, fields, api


class TrainingAlternance(models.Model):
    _name = 'training.alternance'
    _description = "Dossier d'alternance — structure d'accueil"
    _order = 'date_debut desc, id desc'

    inscription_id = fields.Many2one(
        'training.inscription', string='Inscription',
        required=True, ondelete='cascade',
    )
    partner_id = fields.Many2one(
        related='inscription_id.partner_id', store=True, readonly=True,
        string='Stagiaire',
    )
    session_id = fields.Many2one(
        related='inscription_id.session_id', store=True, readonly=True,
        string='Session',
    )

    # ── Structure d'accueil (entreprise) ──────────────────────────
    structure_id = fields.Many2one(
        'res.partner', string="Structure d'accueil",
        domain=[('is_company', '=', True)],
    )
    responsable_id = fields.Many2one(
        'res.partner', string='Responsable de la structure',
        domain=[('is_company', '=', False)],
    )
    tuteur_id = fields.Many2one(
        'res.partner', string='Maître d\'apprentissage / Tuteur',
        domain=[('is_company', '=', False)],
    )

    # ── Poste et missions ─────────────────────────────────────────
    intitule_poste = fields.Char(string='Intitulé du poste')
    missions_principales = fields.Text(string='Missions principales')
    missions_complementaires = fields.Text(string='Missions complémentaires')
    activites_coordination = fields.Text(
        string='Activités de coordination liées au diplôme',
    )
    publics = fields.Char(string='Publics concernés')
    projet_alternance = fields.Text(string='Projet durant l\'alternance')

    # ── Dates d'accueil ───────────────────────────────────────────
    date_debut = fields.Date(string='Date de début d\'accueil')
    date_fin = fields.Date(string='Date de fin d\'accueil')

    # ── Workflow ──────────────────────────────────────────────────
    statut = fields.Selection([
        ('brouillon', 'En cours de saisie'),
        ('soumis',    'Soumis au secrétariat'),
        ('valide',    'Validé'),
        ('archive',   'Archivé'),
    ], string='Statut', default='brouillon', required=True)

    notes_secretariat = fields.Text(string='Notes secrétariat')

    # ── Complétude ────────────────────────────────────────────────
    est_complet = fields.Boolean(
        compute='_compute_est_complet', store=True,
        string='Dossier complet',
    )

    @api.depends('structure_id', 'responsable_id', 'tuteur_id',
                 'intitule_poste', 'missions_principales', 'date_debut')
    def _compute_est_complet(self):
        for rec in self:
            rec.est_complet = bool(
                rec.structure_id and rec.responsable_id and rec.tuteur_id
                and rec.intitule_poste and rec.missions_principales
                and rec.date_debut
            )

    # ── Actions back-office ───────────────────────────────────────
    def action_soumettre(self):
        self.write({'statut': 'soumis'})

    def action_valider(self):
        self.write({'statut': 'valide'})

    def action_archiver(self):
        self.write({'statut': 'archive'})

    # ── Représentation ────────────────────────────────────────────
    def _compute_display_name(self):
        for rec in self:
            if rec.structure_id:
                rec.display_name = rec.structure_id.name
            elif rec.id:
                rec.display_name = f'Dossier #{rec.id}'
            else:
                rec.display_name = 'Nouveau dossier'
